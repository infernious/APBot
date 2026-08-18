import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional, Sequence

import nextcord
from nextcord import Interaction, Member, SlashOption, slash_command
from nextcord.ext import commands
from nextcord.http import Route
from pymongo import ReturnDocument

from app_config import get_command_guild_ids, load_optional_config


logger = logging.getLogger(__name__)
conf = load_optional_config()
COMMAND_GUILD_IDS = get_command_guild_ids(conf)

MEDIA_LEVELING_MANAGER_ROLES = {"Lead Moderator"}

MEDIA_LINK_PATTERN = re.compile(
    r"https?://(?:"
    r"(?:www\.)?tenor\.com/view/[^\s<]+|"
    r"media\.tenor\.com/[^\s<]+|"
    r"(?:www\.)?giphy\.com/gifs/[^\s<]+|"
    r"(?:media\d*|i)\.giphy\.com/[^\s<]+|"
    r"(?:[\w-]+\.)*klipy\.com/[^\s<]+|"
    r"i\.imgur\.com/[^\s<]+|"
    r"(?:cdn|media)\.discordapp\.(?:com|net)/attachments/[^\s<]+|"
    r"[^\s<]+\.(?:png|jpe?g|gif|webp|bmp|mp4|webm|mov)"
    r"(?:\?[^\s<]*)?"
    r")",
    re.IGNORECASE,
)


class MediaLeveling(commands.Cog):
    """Lazy, guild-wide message-based Media Access.

    A member without Media Access receives one exact guild-wide baseline check
    when needed. After that, each new message is added locally and the
    threshold is evaluated again until the role is granted.
    """

    # Increasing this number invalidates older saved baselines. This forces
    # active members without the role to receive one fresh guild-wide check.
    COUNT_VERSION = 2

    TRUSTED_COUNT_SOURCES = {
        "lazy_exact",
        "manual_reset",
    }

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
            int(settings.get("media_link_warning_seconds", 0)),
        )

        # This route has a strict/dynamic Discord limit.
        self.search_requests_per_second = max(
            0.05,
            float(settings.get("search_requests_per_second", 0.75)),
        )
        self.base_search_interval = 1.0 / self.search_requests_per_second
        self.current_search_interval = self.base_search_interval

        database = bot.db.base_db.database
        self.levels = database["media_levels"]
        self.state = database["media_level_state"]

        self.indexes_ready = False
        self.ready_ran = False

        self.search_lock = asyncio.Lock()
        self.last_search_request = 0.0

        # Prevent two rapid messages from resolving the same user twice.
        self.user_locks: dict[int, asyncio.Lock] = {}

        self.search_queries = 0

    async def ensure_indexes(self) -> None:
        if self.indexes_ready:
            return

        await self.levels.create_index(
            [("guild_id", 1), ("user_id", 1)],
            unique=True,
        )
        await self.levels.create_index(
            [("guild_id", 1), ("baseline_complete", 1)],
        )
        await self.state.create_index("guild_id", unique=True)

        self.indexes_ready = True

    def user_lock(self, user_id: int) -> asyncio.Lock:
        lock = self.user_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            self.user_locks[user_id] = lock
        return lock

    @staticmethod
    def can_manage_media_leveling(member: nextcord.Member) -> bool:
        return bool(
            member.guild_permissions.administrator
            or any(
                role.name in MEDIA_LEVELING_MANAGER_ROLES
                for role in member.roles
            )
        )

    def media_role(
        self,
        guild: nextcord.Guild,
    ) -> Optional[nextcord.Role]:
        return guild.get_role(self.media_role_id)

    def bot_can_manage(
        self,
        guild: nextcord.Guild,
        role: nextcord.Role,
    ) -> bool:
        me = guild.me
        return bool(
            me
            and me.guild_permissions.manage_roles
            and me.top_role > role
        )

    async def add_media_role(
        self,
        member: nextcord.Member,
        reason: str,
    ) -> bool:
        role = self.media_role(member.guild)

        if role is None:
            logger.error(
                "[MediaLeveling] Media Access role %s was not found.",
                self.media_role_id,
            )
            return False

        if role in member.roles:
            return True

        if not self.bot_can_manage(member.guild, role):
            logger.error(
                "[MediaLeveling] APBot needs Manage Roles and must be "
                "above %s.",
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

    async def remove_media_role(
        self,
        member: nextcord.Member,
        reason: str,
    ) -> bool:
        role = self.media_role(member.guild)

        if role is None or role not in member.roles:
            return False

        if not self.bot_can_manage(member.guild, role):
            logger.error(
                "[MediaLeveling] Could not remove Media Access from %s. "
                "Check Manage Roles and role hierarchy.",
                member.id,
            )
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

    def document_is_trusted(self, document: Optional[dict]) -> bool:
        return bool(
            document
            and document.get("baseline_complete", False)
            and document.get("count_source") in self.TRUSTED_COUNT_SOURCES
            and int(document.get("count_version", 0)) == self.COUNT_VERSION
        )

    @staticmethod
    def document_total(document: Optional[dict]) -> int:
        if not document:
            return 0

        return (
            int(document.get("historical_messages", 0))
            + int(document.get("live_messages", 0))
        )

    async def wait_for_search_slot(self) -> None:
        async with self.search_lock:
            elapsed = time.monotonic() - self.last_search_request
            delay = self.current_search_interval - elapsed

            if delay > 0:
                await asyncio.sleep(delay)

            self.last_search_request = time.monotonic()

    def increase_search_interval(self, retry_after: float) -> None:
        self.current_search_interval = min(
            300.0,
            max(self.current_search_interval, retry_after),
        )

    def relax_search_interval(self) -> None:
        if self.current_search_interval <= self.base_search_interval:
            self.current_search_interval = self.base_search_interval
            return

        self.current_search_interval = max(
            self.base_search_interval,
            self.current_search_interval * 0.90,
        )

    async def search_message_total(
        self,
        guild_id: int,
        author_ids: Sequence[int],
        *,
        max_id: Optional[int] = None,
    ) -> int:
        """Return Discord's historical message total for the authors."""

        if not author_ids:
            return 0

        if len(author_ids) > 100:
            raise ValueError(
                "Discord permits at most 100 author_id filters."
            )

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
        params.extend(
            ("author_id", str(author_id))
            for author_id in author_ids
        )

        if max_id is not None:
            params.append(("max_id", str(max_id)))

        consecutive_errors = 0

        # Temporary Discord failures should delay one user's check, not crash
        # the entire cog.
        for _ in range(10000):
            await self.wait_for_search_slot()
            self.search_queries += 1

            try:
                response = await self.bot.http.request(
                    route,
                    params=params,
                )

            except nextcord.HTTPException as error:
                status = int(getattr(error, "status", 0) or 0)

                if status == 429:
                    headers = getattr(
                        getattr(error, "response", None),
                        "headers",
                        {},
                    )

                    retry_after = None
                    for header_name in (
                        "Retry-After",
                        "X-RateLimit-Reset-After",
                    ):
                        try:
                            value = headers.get(header_name)
                            if value is not None:
                                retry_after = float(value)
                                break
                        except (
                            AttributeError,
                            TypeError,
                            ValueError,
                        ):
                            pass

                    if retry_after is None:
                        retry_after = min(
                            300.0,
                            10.0
                            * (2 ** min(consecutive_errors, 5)),
                        )

                    retry_after = max(
                        5.0,
                        min(retry_after + 2.0, 300.0),
                    )
                    consecutive_errors += 1
                    self.increase_search_interval(retry_after)

                    logger.warning(
                        "[MediaLeveling] Search rate limited. "
                        "Waiting %.1f seconds.",
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if status in {500, 502, 503, 504}:
                    consecutive_errors += 1
                    retry_after = min(
                        300.0,
                        5.0
                        * (
                            2
                            ** min(
                                consecutive_errors - 1,
                                6,
                            )
                        ),
                    )

                    logger.warning(
                        "[MediaLeveling] Discord search returned %s. "
                        "Waiting %.1f seconds.",
                        status,
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                raise

            except (
                asyncio.TimeoutError,
                ConnectionError,
                OSError,
            ) as error:
                consecutive_errors += 1
                retry_after = min(
                    300.0,
                    5.0
                    * (
                        2
                        ** min(
                            consecutive_errors - 1,
                            6,
                        )
                    ),
                )

                logger.warning(
                    "[MediaLeveling] Temporary %s. Waiting %.1f seconds.",
                    type(error).__name__,
                    retry_after,
                )
                await asyncio.sleep(retry_after)
                continue

            if not isinstance(response, dict):
                consecutive_errors += 1
                await asyncio.sleep(5)
                continue

            consecutive_errors = 0
            self.relax_search_interval()

            if int(response.get("code", 0)) == 110000:
                retry_after = max(
                    1.0,
                    float(response.get("retry_after", 2)),
                )
                await asyncio.sleep(retry_after)
                continue

            if response.get(
                "doing_deep_historical_index",
                False,
            ):
                await asyncio.sleep(5)
                continue

            return max(
                0,
                int(response.get("total_results", 0)),
            )

        raise RuntimeError(
            "Discord message search remained unavailable."
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
        """Check @everyone's channel/category media overwrites."""

        default_role = message.guild.default_role
        channel = message.channel

        # Resolve each permission using the nearest explicit overwrite.
        attach_files: Optional[bool] = None
        embed_links: Optional[bool] = None

        checked_ids: set[int] = set()

        while channel is not None:
            channel_id = getattr(channel, "id", None)
            if channel_id in checked_ids:
                break
            if channel_id is not None:
                checked_ids.add(channel_id)

            try:
                overwrite = channel.overwrites_for(default_role)
            except (AttributeError, TypeError):
                break

            if attach_files is None:
                attach_files = overwrite.attach_files

            if embed_links is None:
                embed_links = overwrite.embed_links

            if attach_files is not None and embed_links is not None:
                break

            channel = getattr(channel, "parent", None)

        return bool(
            attach_files is False
            or embed_links is False
        )

    async def delete_blocked_media_link(
        self,
        message: nextcord.Message,
    ) -> None:
        try:
            await message.delete()
            logger.info(
                "[MediaLeveling] Deleted media link | "
                "channel=%s | user=%s",
                message.channel.id,
                message.author.id,
            )

        except nextcord.NotFound:
            return

        except (nextcord.Forbidden, nextcord.HTTPException):
            logger.exception(
                "[MediaLeveling] Could not delete media link from %s. "
                "APBot needs Manage Messages.",
                message.author.id,
            )
            return

        if self.media_link_warning_seconds <= 0:
            return

        try:
            await message.channel.send(
                (
                    f"{message.author.mention}, you need "
                    f"{self.required_messages} messages before "
                    "posting media here."
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

    async def resolve_member_exactly(
        self,
        message: nextcord.Message,
        *,
        count_current_message: bool,
    ) -> dict:
        """Search one member once and save their exact starting count."""

        historical = await self.search_message_total(
            message.guild.id,
            [message.author.id],
            # Search only messages older than the current message so the
            # current message is never counted twice.
            max_id=max(0, message.id - 1),
        )

        now = datetime.now(timezone.utc)
        live_messages = 1 if count_current_message else 0

        document = await self.levels.find_one_and_update(
            {
                "guild_id": message.guild.id,
                "user_id": message.author.id,
            },
            {
                "$set": {
                    # Store the full count, not a capped count. This makes
                    # future threshold changes easier.
                    "historical_messages": historical,
                    "live_messages": live_messages,
                    "baseline_complete": True,
                    "known_below_threshold": (
                        historical + live_messages
                        < self.required_messages
                    ),
                    "count_source": "lazy_exact",
                    "count_version": self.COUNT_VERSION,
                    "resolved_requirement": self.required_messages,
                    "baseline_resolved_at": now,
                    "last_message_at": (
                        now if count_current_message else None
                    ),
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        logger.info(
            "[MediaLeveling] Lazy-resolved user %s at %s messages.",
            message.author.id,
            self.document_total(document),
        )

        return document

    async def increment_member(
        self,
        message: nextcord.Message,
    ) -> dict:
        now = datetime.now(timezone.utc)

        return await self.levels.find_one_and_update(
            {
                "guild_id": message.guild.id,
                "user_id": message.author.id,
            },
            {
                "$inc": {
                    "live_messages": 1,
                },
                "$set": {
                    "last_message_at": now,
                    "resolved_requirement": self.required_messages,
                },
                "$setOnInsert": {
                    "historical_messages": 0,
                    "baseline_complete": False,
                    "known_below_threshold": True,
                    "count_source": "unresolved",
                    "count_version": self.COUNT_VERSION,
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self.ready_ran:
            return

        self.ready_ran = True
        await self.ensure_indexes()

        await self.state.update_one(
            {"guild_id": self.guild_id},
            {
                "$set": {
                    "status": "lazy_active",
                    "mode": "lazy_exact",
                    "requirement": self.required_messages,
                    "count_version": self.COUNT_VERSION,
                    "enabled": self.enabled,
                    "started_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

        logger.info(
            "[MediaLeveling] Lazy mode ready: enabled=%s, "
            "requirement=%s, search_rps=%s.",
            self.enabled,
            self.required_messages,
            self.search_requests_per_second,
        )

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: nextcord.Member,
    ) -> None:
        if (
            not self.enabled
            or member.bot
            or member.guild.id != self.guild_id
        ):
            return

        await self.ensure_indexes()

        # Preserve a returning member's old document. A member with no record
        # will be checked exactly on their first message.
        await self.levels.update_one(
            {
                "guild_id": member.guild.id,
                "user_id": member.id,
            },
            {
                "$setOnInsert": {
                    "historical_messages": 0,
                    "live_messages": 0,
                    "baseline_complete": False,
                    "known_below_threshold": True,
                    "count_source": "unresolved",
                    "count_version": self.COUNT_VERSION,
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    @commands.Cog.listener()
    async def on_message(
        self,
        message: nextcord.Message,
    ) -> None:
        if (
            not self.enabled
            or message.guild is None
            or message.guild.id != self.guild_id
            or message.author.bot
            or message.webhook_id is not None
            or message.type != nextcord.MessageType.default
            or not isinstance(message.author, nextcord.Member)
        ):
            return

        role = self.media_role(message.guild)
        if role is None:
            return

        # Only members without Media Access are checked. Once the role is
        # granted, normal messages never cause it to be removed.
        if role in message.author.roles:
            return

        contains_media_link = self.contains_blocked_media_link(
            message
        )
        blocked_media_attempt = bool(
            contains_media_link
            and self.channel_restricts_media(message)
        )

        await self.ensure_indexes()

        async with self.user_lock(message.author.id):
            document = await self.levels.find_one(
                {
                    "guild_id": message.guild.id,
                    "user_id": message.author.id,
                }
            )

            if not self.document_is_trusted(document):
                try:
                    document = await self.resolve_member_exactly(
                        message,
                        count_current_message=(
                            not blocked_media_attempt
                        ),
                    )
                except Exception:
                    logger.exception(
                        "[MediaLeveling] Could not lazy-resolve %s.",
                        message.author.id,
                    )

                    # Fail closed for restricted media links.
                    if blocked_media_attempt:
                        await self.delete_blocked_media_link(message)
                    return

            elif not blocked_media_attempt:
                document = await self.increment_member(message)

            total = self.document_total(document)
            qualifies = total >= self.required_messages

            if qualifies:
                role_ready = await self.add_media_role(
                    message.author,
                    (
                        f"Reached {total}/"
                        f"{self.required_messages} messages."
                    ),
                )

                if blocked_media_attempt and not role_ready:
                    await self.delete_blocked_media_link(message)

                return

            if blocked_media_attempt:
                await self.delete_blocked_media_link(message)

    async def require_manager(
        self,
        interaction: Interaction,
    ) -> bool:
        if (
            not isinstance(interaction.user, nextcord.Member)
            or not self.can_manage_media_leveling(interaction.user)
        ):
            await interaction.response.send_message(
                "You need Administrator or the Lead Moderator role.",
                ephemeral=True,
            )
            return False

        return True

    @slash_command(
        name="media-backfill",
        description="Show the current lazy Media Access mode.",
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_backfill(
        self,
        interaction: Interaction,
    ) -> None:
        if not await self.require_manager(interaction):
            return

        await interaction.response.send_message(
            (
                "Full-server backfill is disabled. Lazy checking is active: "
                "a member without Media Access gets one guild-wide baseline "
                "check, then each new message is counted until they qualify."
            ),
            ephemeral=True,
        )

    @slash_command(
        name="media-backfill-status",
        description="Show lazy Media Access statistics.",
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_backfill_status(
        self,
        interaction: Interaction,
    ) -> None:
        if not await self.require_manager(interaction):
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "This command must be used in the server.",
                ephemeral=True,
            )
            return

        resolved = await self.levels.count_documents(
            {
                "guild_id": interaction.guild.id,
                "baseline_complete": True,
                "count_source": {
                    "$in": list(self.TRUSTED_COUNT_SOURCES)
                },
                "count_version": self.COUNT_VERSION,
            }
        )
        stored_members = await self.levels.count_documents(
            {"guild_id": interaction.guild.id}
        )
        unresolved = max(0, stored_members - resolved)

        role = self.media_role(interaction.guild)
        role_members = len(role.members) if role else 0

        await interaction.response.send_message(
            (
                "Status: `lazy active`\n"
                f"Resolved members: `{resolved}`\n"
                f"Pending members: `{unresolved}`\n"
                f"Media Access members: `{role_members}`\n"
                f"Requirement: `{self.required_messages}`"
            ),
            ephemeral=True,
        )

    @slash_command(
        name="media-backfill-stop",
        description="Full backfill is disabled in lazy mode.",
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_backfill_stop(
        self,
        interaction: Interaction,
    ) -> None:
        if not await self.require_manager(interaction):
            return

        await interaction.response.send_message(
            "There is no full-server backfill running.",
            ephemeral=True,
        )

    @slash_command(
        name="media-reset",
        description="Reset one member's Media Access count.",
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
        if not await self.require_manager(interaction):
            return

        if (
            interaction.guild is None
            or interaction.guild.id != self.guild_id
        ):
            await interaction.response.send_message(
                "This command is not configured for this server.",
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
                    "count_source": "manual_reset",
                    "count_version": self.COUNT_VERSION,
                    "resolved_requirement": self.required_messages,
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
            "Media Access count reset by staff.",
        )

        await interaction.response.send_message(
            (
                f"Reset {member.mention} to "
                f"`0/{self.required_messages}`."
                + (
                    " Media Access was removed."
                    if role_removed
                    else ""
                )
            ),
            ephemeral=True,
        )

    @slash_command(
        name="media-recheck",
        description="Recheck a member on their next message.",
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def media_recheck(
        self,
        interaction: Interaction,
        member: Member = SlashOption(
            description="Member to recheck.",
            required=True,
        ),
    ) -> None:
        if not await self.require_manager(interaction):
            return

        if interaction.guild is None:
            return

        await self.ensure_indexes()

        await self.levels.update_one(
            {
                "guild_id": interaction.guild.id,
                "user_id": member.id,
            },
            {
                "$set": {
                    "historical_messages": 0,
                    "live_messages": 0,
                    "baseline_complete": False,
                    "known_below_threshold": True,
                    "count_source": "unresolved",
                    "count_version": self.COUNT_VERSION,
                    "recheck_requested_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

        await self.remove_media_role(
            member,
            "Media Access recheck requested by staff.",
        )

        await interaction.response.send_message(
            (
                f"{member.mention} will be checked exactly "
                "when they next send a message."
            ),
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
            {
                "guild_id": interaction.guild.id,
                "user_id": target.id,
            }
        )

        role = self.media_role(interaction.guild)
        has_role = bool(
            role
            and isinstance(target, nextcord.Member)
            and role in target.roles
        )

        if self.document_is_trusted(document):
            count_text = (
                f"`{self.document_total(document)}/"
                f"{self.required_messages}` messages"
            )
        else:
            count_text = (
                "Pending — their exact count will be checked "
                "on their next message."
            )

        await interaction.response.send_message(
            (
                f"{target.mention}: {count_text}\n"
                f"Media Access: `{'Yes' if has_role else 'No'}`"
            ),
            ephemeral=True,
        )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(MediaLeveling(bot))
