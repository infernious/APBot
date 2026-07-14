import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional, Sequence

import nextcord
from nextcord import Interaction, Member, Permissions, SlashOption, slash_command
from nextcord.ext import commands
from nextcord.http import Route
from pymongo import ReturnDocument, UpdateOne

from app_config import get_command_guild_ids, load_optional_config


logger = logging.getLogger(__name__)
conf = load_optional_config()
COMMAND_GUILD_IDS = get_command_guild_ids(conf)

DISCORD_EPOCH_MS = 1420070400000

MEDIA_LINK_PATTERN = re.compile(
    r"https?://(?:"
    r"(?:www\.)?tenor\.com/view/[^\s<]+|"
    r"media\.tenor\.com/[^\s<]+|"
    r"(?:www\.)?giphy\.com/gifs/[^\s<]+|"
    r"(?:media\d*|i)\.giphy\.com/[^\s<]+|"
    r"i\.imgur\.com/[^\s<]+|"
    r"(?:cdn|media)\.discordapp\.(?:com|net)/attachments/[^\s<]+|"
    r"[^\s<]+\.(?:png|jpe?g|gif|webp|bmp|mp4|webm|mov)"
    r"(?:\?[^\s<]*)?"
    r")",
    re.IGNORECASE,
)


class MediaLeveling(commands.Cog):
    """Grant Media Access after a member reaches a configured message count.

    Historical counts are obtained through Discord's guild-message search API.
    The backfill uses groups of up to 100 authors and only performs individual
    searches when a group may contain somebody over the requirement.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        settings = bot.config.get("media_leveling", {}) or {}
        self.enabled = bool(settings.get("enabled", False))
        self.guild_id = int(bot.config.get("guild_id"))
        self.media_role_id = int(settings.get("media_role_id", 0))
        self.required_messages = max(
            1,
            int(settings.get("required_messages", 1000)),
        )
        self.block_media_links = bool(
            settings.get("block_media_links", True)
        )
        self.media_link_warning_seconds = max(
            0,
            int(settings.get("media_link_warning_seconds", 5)),
        )

        # Keep this low so APBot still has REST capacity for moderation and
        # other features. Nextcord also obeys Discord's own rate-limit headers.
        self.search_requests_per_second = max(
            0.25,
            float(settings.get("search_requests_per_second", 5)),
        )
        self.search_batch_size = min(
            100,
            max(1, int(settings.get("search_batch_size", 100))),
        )
        self.exact_group_size = min(
            self.search_batch_size,
            max(1, int(settings.get("exact_group_size", 8))),
        )

        database = bot.db.base_db.database
        self.levels = database["media_levels"]
        self.state = database["media_level_state"]

        self.indexes_ready = False
        self.ready_ran = False
        self.message_lock = asyncio.Lock()
        self.search_lock = asyncio.Lock()
        self.last_search_request = 0.0
        self.backfill_task: Optional[asyncio.Task] = None
        self.backfill_running = False

        self.search_queries = 0
        self.classified_members = 0
        self.deferred_members = 0
        self.qualified_members = 0

    async def ensure_indexes(self) -> None:
        if self.indexes_ready:
            return

        await self.levels.create_index(
            [("guild_id", 1), ("user_id", 1)],
            unique=True,
        )
        await self.state.create_index("guild_id", unique=True)
        self.indexes_ready = True

    @staticmethod
    def datetime_to_high_snowflake(value: datetime) -> int:
        """Create the greatest Discord snowflake within a UTC millisecond."""

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)

        milliseconds = int(value.timestamp() * 1000)
        return ((milliseconds - DISCORD_EPOCH_MS) << 22) + ((1 << 22) - 1)

    def media_role(self, guild: nextcord.Guild) -> Optional[nextcord.Role]:
        return guild.get_role(self.media_role_id)

    def bot_can_manage(self, guild: nextcord.Guild, role: nextcord.Role) -> bool:
        me = guild.me
        return bool(
            me
            and me.guild_permissions.manage_roles
            and me.top_role > role
        )

    async def add_media_role(self, member: nextcord.Member, reason: str) -> bool:
        role = self.media_role(member.guild)
        if role is None or role in member.roles:
            return False

        if not self.bot_can_manage(member.guild, role):
            logger.error(
                "[MediaLeveling] APBot needs Manage Roles and must be above %s.",
                role.name,
            )
            return False

        try:
            await member.add_roles(role, reason=reason)
            return True
        except (nextcord.Forbidden, nextcord.HTTPException):
            logger.exception(
                "[MediaLeveling] Could not add Media Access to %s.",
                member.id,
            )
            return False

    async def remove_media_role(self, member: nextcord.Member, reason: str) -> bool:
        role = self.media_role(member.guild)
        if role is None or role not in member.roles:
            return False

        if not self.bot_can_manage(member.guild, role):
            return False

        try:
            await member.remove_roles(role, reason=reason)
            return True
        except (nextcord.Forbidden, nextcord.HTTPException):
            logger.exception(
                "[MediaLeveling] Could not remove Media Access from %s.",
                member.id,
            )
            return False

    async def fetch_members(self, guild: nextcord.Guild) -> list[nextcord.Member]:
        try:
            return [
                member
                async for member in guild.fetch_members(limit=None)
                if not member.bot
            ]
        except (nextcord.Forbidden, nextcord.HTTPException):
            logger.exception(
                "[MediaLeveling] Member fetch failed; using cached members."
            )
            return [member for member in guild.members if not member.bot]

    async def edit_progress(
        self,
        message: nextcord.Message,
        content: str,
    ) -> None:
        try:
            await message.edit(content=content)
        except (nextcord.Forbidden, nextcord.HTTPException):
            pass

    async def wait_for_search_slot(self) -> None:
        interval = 1.0 / self.search_requests_per_second

        async with self.search_lock:
            elapsed = time.monotonic() - self.last_search_request
            delay = interval - elapsed
            if delay > 0:
                await asyncio.sleep(delay)
            self.last_search_request = time.monotonic()

    async def search_message_total(
        self,
        guild_id: int,
        author_ids: Sequence[int],
        *,
        max_id: Optional[int] = None,
    ) -> int:
        """Return Discord's total search result count for the supplied authors."""

        if not author_ids:
            return 0
        if len(author_ids) > 100:
            raise ValueError("Discord permits at most 100 author_id filters.")

        route = Route(
            "GET",
            "/guilds/{guild_id}/messages/search",
            guild_id=guild_id,
        )

        params: list[tuple[str, str]] = [
            ("limit", "1"),
            ("author_type", "user"),
            ("sort_by", "timestamp"),
            ("sort_order", "desc"),
        ]
        params.extend(("author_id", str(author_id)) for author_id in author_ids)

        if max_id is not None:
            params.append(("max_id", str(max_id)))

        # A guild can need search indexing the first time this endpoint is used.
        # Retry the documented "index not yet available" response.
        for attempt in range(240):
            await self.wait_for_search_slot()
            self.search_queries += 1

            response = await self.bot.http.request(route, params=params)
            if not isinstance(response, dict):
                raise RuntimeError("Discord returned an invalid search response.")

            if int(response.get("code", 0)) == 110000:
                retry_after = max(1.0, float(response.get("retry_after", 2)))
                await asyncio.sleep(retry_after)
                continue

            if response.get("doing_deep_historical_index", False):
                # Avoid classifying members from a partial historical index.
                await self.state.update_one(
                    {"guild_id": guild_id},
                    {
                        "$set": {
                            "search_indexing": True,
                            "documents_indexed": int(
                                response.get("documents_indexed", 0)
                            ),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
                await asyncio.sleep(5)
                continue

            return max(0, int(response.get("total_results", 0)))

        raise RuntimeError(
            "Discord's guild message-search index did not become ready."
        )

    async def reset_member_documents(
        self,
        guild_id: int,
        members: list[nextcord.Member],
        cutoff: datetime,
        cutoff_id: int,
    ) -> None:
        operations: list[UpdateOne] = []

        for member in members:
            operations.append(
                UpdateOne(
                    {"guild_id": guild_id, "user_id": member.id},
                    {
                        "$set": {
                            "historical_messages": 0,
                            "live_messages": 0,
                            "baseline_complete": False,
                            "known_below_threshold": False,
                            "backfill_complete": False,
                            "backfill_started_at": cutoff,
                            "backfill_cutoff_id": cutoff_id,
                        },
                        "$setOnInsert": {"created_at": cutoff},
                    },
                    upsert=True,
                )
            )

            if len(operations) == 500:
                await self.levels.bulk_write(operations, ordered=False)
                operations.clear()

        if operations:
            await self.levels.bulk_write(operations, ordered=False)

    async def save_classification(
        self,
        guild_id: int,
        known_counts: dict[int, int],
        deferred_ids: set[int],
    ) -> None:
        now = datetime.now(timezone.utc)
        operations: list[UpdateOne] = []

        for user_id, count in known_counts.items():
            operations.append(
                UpdateOne(
                    {"guild_id": guild_id, "user_id": user_id},
                    {
                        "$set": {
                            "historical_messages": min(
                                count,
                                self.required_messages,
                            ),
                            "baseline_complete": True,
                            "known_below_threshold": (
                                count < self.required_messages
                            ),
                            "backfill_complete": True,
                            "backfill_completed_at": now,
                        }
                    },
                    upsert=True,
                )
            )

            if len(operations) == 500:
                await self.levels.bulk_write(operations, ordered=False)
                operations.clear()

        for user_id in deferred_ids:
            operations.append(
                UpdateOne(
                    {"guild_id": guild_id, "user_id": user_id},
                    {
                        "$set": {
                            "historical_messages": 0,
                            "baseline_complete": False,
                            "known_below_threshold": True,
                            "backfill_complete": True,
                            "backfill_completed_at": now,
                        }
                    },
                    upsert=True,
                )
            )

            if len(operations) == 500:
                await self.levels.bulk_write(operations, ordered=False)
                operations.clear()

        if operations:
            await self.levels.bulk_write(operations, ordered=False)

    async def classify_members(
        self,
        guild: nextcord.Guild,
        members: list[nextcord.Member],
        cutoff_id: int,
        progress: nextcord.Message,
    ) -> tuple[dict[int, int], set[int]]:
        """Classify members with grouped search queries.

        A group whose combined message total is below the requirement cannot
        contain an individually qualified member. Those members are deferred;
        their exact total is fetched only when they next send a message.
        """

        known_counts: dict[int, int] = {}
        deferred_ids: set[int] = set()
        stack: list[list[nextcord.Member]] = []

        for index in range(0, len(members), self.search_batch_size):
            stack.append(members[index : index + self.search_batch_size])

        last_update = 0.0

        while stack:
            group = stack.pop()
            author_ids = [member.id for member in group]
            group_total = await self.search_message_total(
                guild.id,
                author_ids,
                max_id=cutoff_id,
            )

            if group_total < self.required_messages:
                deferred_ids.update(author_ids)
                self.deferred_members += len(group)
                self.classified_members += len(group)

            elif len(group) == 1:
                user_id = group[0].id
                known_counts[user_id] = group_total
                self.classified_members += 1
                if group_total >= self.required_messages:
                    self.qualified_members += 1

            elif len(group) <= self.exact_group_size:
                for member in group:
                    individual_total = await self.search_message_total(
                        guild.id,
                        [member.id],
                        max_id=cutoff_id,
                    )
                    known_counts[member.id] = individual_total
                    self.classified_members += 1
                    if individual_total >= self.required_messages:
                        self.qualified_members += 1

            else:
                midpoint = len(group) // 2
                stack.append(group[:midpoint])
                stack.append(group[midpoint:])

            now = time.monotonic()
            if now - last_update >= 10 or not stack:
                last_update = now
                await self.state.update_one(
                    {"guild_id": guild.id},
                    {
                        "$set": {
                            "search_queries": self.search_queries,
                            "members_classified": self.classified_members,
                            "members_deferred": self.deferred_members,
                            "members_qualified": self.qualified_members,
                            "groups_remaining": len(stack),
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )
                await self.edit_progress(
                    progress,
                    "**Media backfill**\n"
                    f"Progress: `{self.classified_members}/{len(members)}`",
                )

        return known_counts, deferred_ids

    async def resolve_members_active_during_backfill(
        self,
        guild: nextcord.Guild,
        progress: nextcord.Message,
    ) -> int:
        """Resolve deferred members who sent messages during the backfill."""

        user_ids: list[int] = []
        cursor = self.levels.find(
            {
                "guild_id": guild.id,
                "baseline_complete": False,
                "live_messages": {"$gt": 0},
            },
            {"user_id": 1},
        )
        async for document in cursor:
            user_ids.append(int(document["user_id"]))

        if not user_ids:
            return 0

        await self.edit_progress(
            progress,
            "**Media backfill**\n"
            f"Checking active members: `0/{len(user_ids)}`",
        )

        resolved = 0
        for user_id in user_ids:
            total = await self.search_message_total(guild.id, [user_id])
            await self.levels.update_one(
                {"guild_id": guild.id, "user_id": user_id},
                {
                    "$set": {
                        "historical_messages": min(
                            total,
                            self.required_messages,
                        ),
                        "live_messages": 0,
                        "baseline_complete": True,
                        "known_below_threshold": (
                            total < self.required_messages
                        ),
                        "baseline_resolved_at": datetime.now(timezone.utc),
                    }
                },
            )
            resolved += 1

            if resolved % 50 == 0 or resolved == len(user_ids):
                await self.edit_progress(
                    progress,
                    "**Media backfill**\n"
                    f"Checking active members: `{resolved}/{len(user_ids)}`",
                )

        return resolved

    async def reconcile_roles(
        self,
        guild: nextcord.Guild,
        members: list[nextcord.Member],
        progress: nextcord.Message,
    ) -> tuple[int, int]:
        documents: dict[int, dict] = {}
        async for document in self.levels.find({"guild_id": guild.id}):
            documents[int(document["user_id"])] = document

        added = 0
        removed = 0

        for index, old_member in enumerate(members, start=1):
            member = guild.get_member(old_member.id)
            if member is None or member.bot:
                continue

            document = documents.get(member.id, {})
            baseline_complete = bool(document.get("baseline_complete", False))
            total = int(document.get("historical_messages", 0)) + int(
                document.get("live_messages", 0)
            )
            qualifies = baseline_complete and total >= self.required_messages

            changed = False
            if qualifies:
                changed = await self.add_media_role(
                    member,
                    f"Reached at least {self.required_messages} messages.",
                )
                if changed:
                    added += 1
            else:
                changed = await self.remove_media_role(
                    member,
                    f"Below requirement of {self.required_messages} messages.",
                )
                if changed:
                    removed += 1

            if index % 250 == 0 or index == len(members):
                await self.edit_progress(
                    progress,
                    "**Media backfill**\n"
                    f"Applying roles: `{index}/{len(members)}`",
                )

            if changed:
                await asyncio.sleep(0.05)

        return added, removed

    async def run_backfill(
        self,
        guild: nextcord.Guild,
        progress: nextcord.Message,
        started_by: int,
    ) -> None:
        started = time.monotonic()
        self.backfill_running = True
        self.search_queries = 0
        self.classified_members = 0
        self.deferred_members = 0
        self.qualified_members = 0

        try:
            await self.ensure_indexes()
            members = await self.fetch_members(guild)

            async with self.message_lock:
                cutoff = datetime.now(timezone.utc)
                cutoff_id = self.datetime_to_high_snowflake(cutoff)
                await self.reset_member_documents(
                    guild.id,
                    members,
                    cutoff,
                    cutoff_id,
                )
                await self.state.update_one(
                    {"guild_id": guild.id},
                    {
                        "$set": {
                            "status": "running",
                            "method": "guild_message_search",
                            "scan_cutoff": cutoff,
                            "scan_cutoff_id": cutoff_id,
                            "started_at": cutoff,
                            "started_by": started_by,
                            "members_total": len(members),
                            "search_queries": 0,
                            "members_classified": 0,
                            "members_deferred": 0,
                            "members_qualified": 0,
                            "search_indexing": False,
                        }
                    },
                    upsert=True,
                )

            await self.edit_progress(
                progress,
                "**Media backfill**\n"
                f"Progress: `0/{len(members)}`",
            )

            known_counts, deferred_ids = await self.classify_members(
                guild,
                members,
                cutoff_id,
                progress,
            )
            await self.save_classification(
                guild.id,
                known_counts,
                deferred_ids,
            )

            active_resolved = await self.resolve_members_active_during_backfill(
                guild,
                progress,
            )

            await self.edit_progress(
                progress,
                "**Media backfill**\n"
                f"Applying roles: `0/{len(members)}`",
            )
            added, removed = await self.reconcile_roles(guild, members, progress)
            elapsed = int(time.monotonic() - started)

            await self.state.update_one(
                {"guild_id": guild.id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc),
                        "members_total": len(members),
                        "members_classified": self.classified_members,
                        "members_deferred": self.deferred_members,
                        "members_qualified": self.qualified_members,
                        "active_members_resolved": active_resolved,
                        "search_queries": self.search_queries,
                        "roles_added": added,
                        "roles_removed": removed,
                        "runtime_seconds": elapsed,
                        "search_indexing": False,
                    }
                },
            )

            await self.edit_progress(
                progress,
                "✅ **Media backfill complete.**",
            )

        except asyncio.CancelledError:
            await self.state.update_one(
                {"guild_id": guild.id},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            await self.edit_progress(progress, "**Media backfill stopped.**")
            raise

        except Exception as error:
            logger.exception("[MediaLeveling] Search backfill failed.")
            await self.state.update_one(
                {"guild_id": guild.id},
                {
                    "$set": {
                        "status": "failed",
                        "failed_at": datetime.now(timezone.utc),
                        "error": f"{type(error).__name__}: {error}",
                    }
                },
                upsert=True,
            )
            await self.edit_progress(
                progress,
                "❌ **Media backfill failed. Check the console.**",
            )

        finally:
            self.backfill_running = False
            self.backfill_task = None

    async def initialize_deferred_member(
        self,
        message: nextcord.Message,
    ) -> dict:
        """Fetch one member's exact pre-message count, then count this message."""

        historical = await self.search_message_total(
            message.guild.id,
            [message.author.id],
            max_id=message.id,
        )
        now = datetime.now(timezone.utc)

        document = await self.levels.find_one_and_update(
            {
                "guild_id": message.guild.id,
                "user_id": message.author.id,
            },
            {
                "$set": {
                    "historical_messages": min(
                        historical,
                        self.required_messages,
                    ),
                    # The search used max_id=message.id, so it excludes this
                    # message. Start the live portion at exactly one.
                    "live_messages": 1,
                    "baseline_complete": True,
                    "known_below_threshold": (
                        historical < self.required_messages
                    ),
                    "baseline_resolved_at": now,
                    "last_message_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return document

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self.ready_ran:
            return

        self.ready_ran = True
        await self.ensure_indexes()

        state = await self.state.find_one({"guild_id": self.guild_id})
        if state and state.get("status") == "running":
            await self.state.update_one(
                {"guild_id": self.guild_id},
                {
                    "$set": {
                        "status": "interrupted",
                        "interrupted_at": datetime.now(timezone.utc),
                    }
                },
            )

        logger.info(
            "[MediaLeveling] Ready: enabled=%s, requirement=%s, search_rps=%s.",
            self.enabled,
            self.required_messages,
            self.search_requests_per_second,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: nextcord.Member) -> None:
        if not self.enabled or member.bot or member.guild.id != self.guild_id:
            return

        await self.ensure_indexes()
        document = await self.levels.find_one(
            {"guild_id": member.guild.id, "user_id": member.id}
        )

        if document:
            total = int(document.get("historical_messages", 0)) + int(
                document.get("live_messages", 0)
            )
            if bool(document.get("baseline_complete", False)) and total >= self.required_messages:
                await self.add_media_role(
                    member,
                    f"Restored Media Access at {total} messages.",
                )
                return

        await self.levels.update_one(
            {"guild_id": member.guild.id, "user_id": member.id},
            {
                "$setOnInsert": {
                    "historical_messages": 0,
                    "live_messages": 0,
                    # Brand-new members have no pre-join server messages.
                    "baseline_complete": True,
                    "known_below_threshold": True,
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    def contains_blocked_media_link(
        self,
        message: nextcord.Message,
    ) -> bool:
        return bool(
            self.block_media_links
            and message.content
            and MEDIA_LINK_PATTERN.search(message.content)
        )

    def channel_restricts_media(
        self,
        message: nextcord.Message,
    ) -> bool:
        """Return True when @everyone is explicitly denied media here."""

        channel = message.channel

        # Threads inherit permissions from their parent channel.
        parent = getattr(channel, "parent", None)
        if parent is not None:
            channel = parent

        try:
            overwrite = channel.overwrites_for(message.guild.default_role)
        except (AttributeError, TypeError):
            return False

        return bool(
            overwrite.embed_links is False
            or overwrite.attach_files is False
        )

    async def delete_blocked_media_link(
        self,
        message: nextcord.Message,
    ) -> None:
        try:
            await message.delete()
            logger.info(
                "[MediaLeveling] deleted blocked media link | channel=%s | user=%s",
                message.channel.id,
                message.author.id,
            )
        except nextcord.NotFound:
            logger.info(
                "[MediaLeveling] media link was already deleted | channel=%s | user=%s",
                message.channel.id,
                message.author.id,
            )
            return
        except (nextcord.Forbidden, nextcord.HTTPException):
            logger.exception(
                "[MediaLeveling] Could not delete media link from %s. "
                "APBot needs Manage Messages in this channel.",
                message.author.id,
            )
            return

        if self.media_link_warning_seconds <= 0:
            return

        try:
            await message.channel.send(
                (
                    f"{message.author.mention}, you need "
                    f"{self.required_messages} messages before posting media here."
                ),
                delete_after=self.media_link_warning_seconds,
                allowed_mentions=nextcord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )
        except (nextcord.Forbidden, nextcord.HTTPException):
            pass

    async def resolve_count_before_message(
        self,
        message: nextcord.Message,
        document: Optional[dict],
    ) -> Optional[dict]:
        """Resolve a deferred count without counting the current message."""

        if document and bool(document.get("baseline_complete", False)):
            return document

        if self.backfill_running:
            return document

        historical = await self.search_message_total(
            message.guild.id,
            [message.author.id],
            max_id=message.id,
        )
        now = datetime.now(timezone.utc)

        return await self.levels.find_one_and_update(
            {
                "guild_id": message.guild.id,
                "user_id": message.author.id,
            },
            {
                "$set": {
                    "historical_messages": min(
                        historical,
                        self.required_messages,
                    ),
                    "live_messages": 0,
                    "baseline_complete": True,
                    "known_below_threshold": (
                        historical < self.required_messages
                    ),
                    "baseline_resolved_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message) -> None:
        if (
            not self.enabled
            or message.guild is None
            or message.guild.id != self.guild_id
            or message.author.bot
            or message.webhook_id is not None
            or not isinstance(message.author, nextcord.Member)
        ):
            return

        role = self.media_role(message.guild)
        if role is None or role in message.author.roles:
            return

        await self.ensure_indexes()

        contains_media_link = self.contains_blocked_media_link(message)
        restricted_channel = self.channel_restricts_media(message)
        should_block_media_link = (
            contains_media_link
            and restricted_channel
        )

        if contains_media_link:
            logger.info(
                "[MediaLeveling] media link seen | guild=%s | channel=%s | "
                "user=%s | restricted=%s | has_media_role=%s",
                message.guild.id,
                message.channel.id,
                message.author.id,
                restricted_channel,
                role in message.author.roles,
            )

        if should_block_media_link:
            try:
                async with self.message_lock:
                    document = await self.levels.find_one(
                        {
                            "guild_id": message.guild.id,
                            "user_id": message.author.id,
                        }
                    )
                    document = await self.resolve_count_before_message(
                        message,
                        document,
                    )
            except Exception:
                logger.exception(
                    "[MediaLeveling] Could not verify media access for %s.",
                    message.author.id,
                )
                document = None

            total = (
                int(document.get("historical_messages", 0))
                + int(document.get("live_messages", 0))
                if document
                else 0
            )
            baseline_complete = bool(
                document and document.get("baseline_complete", False)
            )

            if baseline_complete and total >= self.required_messages:
                role_added = await self.add_media_role(
                    message.author,
                    f"Reached {total}/{self.required_messages} messages.",
                )

                refreshed_member = message.guild.get_member(message.author.id)
                has_role_now = bool(
                    refreshed_member
                    and role in refreshed_member.roles
                )

                if role_added or has_role_now:
                    return

                logger.warning(
                    "[MediaLeveling] %s qualified at %s/%s, but Media Access "
                    "could not be assigned. Deleting the media link.",
                    message.author.id,
                    total,
                    self.required_messages,
                )

            await self.delete_blocked_media_link(message)
            return

        async with self.message_lock:
            document = await self.levels.find_one(
                {
                    "guild_id": message.guild.id,
                    "user_id": message.author.id,
                }
            )

            baseline_complete = bool(
                document and document.get("baseline_complete", False)
            )

            if not baseline_complete and not self.backfill_running:
                try:
                    document = await self.initialize_deferred_member(message)
                except Exception:
                    logger.exception(
                        "[MediaLeveling] Could not initialize count for %s.",
                        message.author.id,
                    )
                    # Keep counting locally. A later message can retry search.
                    document = await self.levels.find_one_and_update(
                        {
                            "guild_id": message.guild.id,
                            "user_id": message.author.id,
                        },
                        {
                            "$inc": {"live_messages": 1},
                            "$set": {
                                "last_message_at": datetime.now(timezone.utc)
                            },
                            "$setOnInsert": {
                                "historical_messages": 0,
                                "baseline_complete": False,
                                "known_below_threshold": True,
                                "created_at": datetime.now(timezone.utc),
                            },
                        },
                        upsert=True,
                        return_document=ReturnDocument.AFTER,
                    )

            else:
                document = await self.levels.find_one_and_update(
                    {
                        "guild_id": message.guild.id,
                        "user_id": message.author.id,
                    },
                    {
                        "$inc": {"live_messages": 1},
                        "$set": {
                            "last_message_at": datetime.now(timezone.utc)
                        },
                        "$setOnInsert": {
                            "historical_messages": 0,
                            "baseline_complete": not self.backfill_running,
                            "known_below_threshold": True,
                            "created_at": datetime.now(timezone.utc),
                        },
                    },
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )

        total = int(document.get("historical_messages", 0)) + int(
            document.get("live_messages", 0)
        )
        baseline_complete = bool(document.get("baseline_complete", False))

        if baseline_complete and total >= self.required_messages:
            await self.add_media_role(
                message.author,
                f"Reached {total}/{self.required_messages} messages.",
            )

    @slash_command(
        name="media-backfill",
        description="Use Discord search to calculate Media Access eligibility.",
        default_member_permissions=Permissions(administrator=True),
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_backfill(self, interaction: Interaction) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This command is not configured for this server.",
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need Administrator to run this command.",
                ephemeral=True,
            )
            return

        if not self.enabled:
            await interaction.response.send_message(
                "`media_leveling.enabled` is false in config.json.",
                ephemeral=True,
            )
            return

        role = self.media_role(interaction.guild)
        if role is None:
            await interaction.response.send_message(
                "The configured `media_role_id` does not exist.",
                ephemeral=True,
            )
            return

        if not self.bot_can_manage(interaction.guild, role):
            await interaction.response.send_message(
                "Give APBot **Manage Roles** and move APBot above Media Access.",
                ephemeral=True,
            )
            return

        if self.backfill_task and not self.backfill_task.done():
            await interaction.response.send_message(
                "A media backfill is already running.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Started.",
            ephemeral=True,
        )
        progress = await interaction.channel.send(
            "**Starting media backfill...**"
        )
        self.backfill_task = asyncio.create_task(
            self.run_backfill(
                interaction.guild,
                progress,
                interaction.user.id,
            )
        )

    @slash_command(
        name="media-backfill-stop",
        description="Stop the currently running Media Access backfill.",
        default_member_permissions=Permissions(administrator=True),
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_backfill_stop(self, interaction: Interaction) -> None:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need Administrator to run this command.",
                ephemeral=True,
            )
            return

        if self.backfill_task is None or self.backfill_task.done():
            await interaction.response.send_message(
                "No media backfill is currently running.",
                ephemeral=True,
            )
            return

        self.backfill_task.cancel()
        await interaction.response.send_message(
            "Stopping the media backfill...",
            ephemeral=True,
        )

    @slash_command(
        name="media-backfill-status",
        description="Show the Media Access backfill status.",
        default_member_permissions=Permissions(administrator=True),
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_backfill_status(self, interaction: Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command must be used in a server.",
                ephemeral=True,
            )
            return

        state = await self.state.find_one({"guild_id": interaction.guild.id})
        if state is None:
            await interaction.response.send_message(
                "No media backfill has been started.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Status: `{state.get('status', 'unknown')}`\n"
            f"Progress: `{state.get('members_classified', 0)}/"
            f"{state.get('members_total', 0)}`",
            ephemeral=True,
        )

    @slash_command(
        name="media-reset",
        description="Reset one member's Media Access count for testing.",
        default_member_permissions=Permissions(administrator=True),
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_reset(
        self,
        interaction: Interaction,
        member: Member = SlashOption(
            description="Member whose count should be reset.",
            required=True,
        ),
    ) -> None:
        if interaction.guild is None or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This command is not configured for this server.",
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "You need Administrator to run this command.",
                ephemeral=True,
            )
            return

        await self.ensure_indexes()
        now = datetime.now(timezone.utc)

        await self.levels.update_one(
            {
                "guild_id": interaction.guild.id,
                "user_id": member.id,
            },
            {
                "$set": {
                    "historical_messages": 0,
                    "live_messages": 0,
                    "baseline_complete": True,
                    "known_below_threshold": True,
                    "backfill_complete": True,
                    "reset_at": now,
                    "last_message_at": None,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

        role_removed = await self.remove_media_role(
            member,
            "Media Access count reset by an administrator.",
        )

        await interaction.response.send_message(
            f"Reset {member.mention} to `0/{self.required_messages}`."
            + (" Media Access was removed." if role_removed else ""),
            ephemeral=True,
        )

    @slash_command(
        name="media-count",
        description="Check a member's stored Media Access count.",
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_count(
        self,
        interaction: Interaction,
        member: Member = SlashOption(
            description="Leave blank to check yourself.",
            required=False,
            default=None,
        ),
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command must be used in a server.",
                ephemeral=True,
            )
            return

        target = member or interaction.user
        document = await self.levels.find_one(
            {"guild_id": interaction.guild.id, "user_id": target.id}
        )

        historical = int(document.get("historical_messages", 0)) if document else 0
        live = int(document.get("live_messages", 0)) if document else 0
        baseline_complete = bool(
            document and document.get("baseline_complete", False)
        )
        total = historical + live
        remaining = max(0, self.required_messages - total)

        role = self.media_role(interaction.guild)
        has_role = bool(role and role in target.roles)

        if baseline_complete:
            count_text = f"`{total}/{self.required_messages}` messages"
        else:
            count_text = "Count pending until their next message."

        await interaction.response.send_message(
            f"{target.mention}: {count_text}\n"
            f"Media Access: `{'Yes' if has_role else 'No'}`",
            ephemeral=True,
        )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(MediaLeveling(bot))
