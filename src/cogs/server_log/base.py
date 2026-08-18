from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

import nextcord
from nextcord.ext import commands

from bot_base import APBot


SERVER_LOG_CHANNEL_KEY = "server_log_channel_id"
SERVER_LOG_CHANNEL_NAME = "server-log"

IGNORED_ROLES_KEY = "server_log_ignored_role_ids"
IGNORED_CHANNELS_KEY = "server_log_ignored_channel_ids"

FIELD_LIMIT = 1024
DESCRIPTION_LIMIT = 4096

# Discord writes audit log entries asynchronously, so the entry for an event is
# often not readable on the first lookup. One cheap retry catches most of them.
AUDIT_ATTEMPTS = 2
AUDIT_RETRY_DELAY = 1.0
AUDIT_WINDOW_SECONDS = 15.0
AUDIT_SCAN_LIMIT = 8


def clip(text: Optional[str], limit: int = FIELD_LIMIT) -> str:
    """Trims text so it fits inside an embed field or description."""
    if not text:
        return ""

    if len(text) <= limit:
        return text

    return text[: limit - 20].rstrip() + "\n... *(cut off)*"


def config_get(bot, key: str, default: Any = None) -> Any:
    config = getattr(bot, "config", None)

    if config is None:
        return default

    return config.get(key, default)


def config_id_set(bot, key: str) -> set[int]:
    """Reads a config list of snowflakes, skipping anything non-numeric."""
    raw = config_get(bot, key) or []

    if isinstance(raw, (str, int)):
        raw = [raw]

    ids: set[int] = set()

    for value in raw:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue

    return ids


def is_sendable(channel) -> bool:
    return channel is not None and hasattr(channel, "send")


def resolve_log_channel(bot, guild):
    """
    Resolves the channel every server log is posted to.

    Prefers the `server_log_channel_id` config value. Falls back to a channel
    named `server-log` so the cogs still work on a fresh install, and so an
    unresolvable ID does not silently kill all logging.
    """
    raw_id = config_get(bot, SERVER_LOG_CHANNEL_KEY)

    if raw_id:
        try:
            channel_id = int(raw_id)
        except (TypeError, ValueError):
            channel_id = None

        if channel_id:
            channel = None

            if guild is not None and hasattr(guild, "get_channel"):
                channel = guild.get_channel(channel_id)

            if channel is None and hasattr(bot, "get_channel"):
                channel = bot.get_channel(channel_id)

            if is_sendable(channel):
                return channel

    if guild is not None:
        channel = nextcord.utils.get(
            getattr(guild, "text_channels", None) or [],
            name=SERVER_LOG_CHANNEL_NAME,
        )

        if is_sendable(channel):
            return channel

    return None


def format_user(user) -> str:
    """Standard `mention / name / id` block used across every log embed."""
    if user is None:
        return "Unknown"

    user_id = getattr(user, "id", None)
    mention = getattr(user, "mention", None) or (f"<@{user_id}>" if user_id else "Unknown")
    name = getattr(user, "display_name", None) or getattr(user, "name", None) or str(user)

    return f"{mention}\n`{name}` (`{user_id if user_id is not None else 'unknown'}`)"


def format_channel(channel) -> str:
    if channel is None:
        return "Unknown"

    channel_id = getattr(channel, "id", None)
    mention = getattr(channel, "mention", None) or (f"<#{channel_id}>" if channel_id else "Unknown")
    name = getattr(channel, "name", None) or "unknown"

    return f"{mention}\n`{name}` (`{channel_id if channel_id is not None else 'unknown'}`)"


def format_timestamp(moment: Optional[datetime]) -> str:
    if moment is None:
        return "Unknown"

    epoch = int(moment.timestamp())
    return f"<t:{epoch}:F> (<t:{epoch}:R>)"


def is_default_role(role) -> bool:
    """True for @everyone, which is never worth listing."""
    is_default = getattr(role, "is_default", None)

    if callable(is_default):
        try:
            return bool(is_default())
        except Exception:
            pass

    return getattr(role, "name", "") == "@everyone"


def audit_touched(entry, *attribute_names: str) -> bool:
    """
    True when an audit entry's diff actually mentions one of `attribute_names`.

    Several distinct member changes share the `member_update` action, so without
    this a nickname edit can be misreported as the actor behind a timeout.
    """
    changes = getattr(entry, "changes", None)

    if changes is None:
        return True

    for side_name in ("before", "after"):
        side = getattr(changes, side_name, None)

        if side is None:
            continue

        for name in attribute_names:
            if getattr(side, name, None) is not None:
                return True

    return False


def format_role_list(roles: Iterable, limit: int = 25) -> str:
    """Renders roles newest-first, matching how Discord displays them."""
    ordered = [role for role in roles if not is_default_role(role)]
    ordered.sort(key=lambda role: getattr(role, "position", 0), reverse=True)

    if not ordered:
        return "None"

    shown = [getattr(role, "mention", None) or f"`{getattr(role, 'name', 'unknown')}`" for role in ordered[:limit]]
    text = ", ".join(shown)

    if len(ordered) > limit:
        text += f", +{len(ordered) - limit} more"

    return clip(text)


def prettify_flag(name: str) -> str:
    """`manage_messages` -> `Manage Messages`."""
    return name.replace("_", " ").title()


def diff_permissions(before, after) -> tuple[list[str], list[str]]:
    """Returns (granted, revoked) permission names between two Permissions sets."""
    granted: list[str] = []
    revoked: list[str] = []

    if before is None or after is None:
        return granted, revoked

    for name, value in after:
        was_set = bool(getattr(before, name, False))

        if value and not was_set:
            granted.append(name)
        elif was_set and not value:
            revoked.append(name)

    return granted, revoked


def format_permission_names(names: list[str], limit: int = 20) -> str:
    if not names:
        return "None"

    shown = [f"`{prettify_flag(name)}`" for name in sorted(names)[:limit]]
    text = ", ".join(shown)

    if len(names) > limit:
        text += f", +{len(names) - limit} more"

    return clip(text)


async def find_audit_entry(
    guild,
    action,
    *,
    target_id: Optional[int] = None,
    check: Optional[Callable[[Any], bool]] = None,
    within: float = AUDIT_WINDOW_SECONDS,
    limit: int = AUDIT_SCAN_LIMIT,
    attempts: int = AUDIT_ATTEMPTS,
    delay: Optional[float] = None,
):
    """
    Finds the audit log entry responsible for an event.

    `within` guards against attributing an old entry to a new event, which is the
    main failure mode of audit-log correlation. Returns None when the bot lacks
    View Audit Log, when nothing matches, or on any API error.
    """
    if guild is None:
        return None

    me = getattr(guild, "me", None)

    if me is None:
        return None

    permissions = getattr(me, "guild_permissions", None)

    if permissions is None or not getattr(permissions, "view_audit_log", False):
        return None

    # Read at call time so the retry pacing stays patchable.
    retry_delay = AUDIT_RETRY_DELAY if delay is None else delay

    for attempt in range(max(1, attempts)):
        if attempt:
            await asyncio.sleep(retry_delay)

        try:
            now = datetime.now(timezone.utc)

            async for entry in guild.audit_logs(limit=limit, action=action):
                created_at = getattr(entry, "created_at", None)

                if created_at and (now - created_at).total_seconds() > within:
                    continue

                if target_id is not None and getattr(entry.target, "id", None) != target_id:
                    continue

                if check is not None and not check(entry):
                    continue

                return entry

        except Exception:
            # Audit lookups are best-effort; a failure must never break the log.
            return None

    return None


class ServerLogCog(commands.Cog):
    """
    Shared plumbing for the server log cogs.

    Every subclass posts to the single channel resolved by `resolve_log_channel`,
    and only for the guild in `guild_id` so the ban-appeal server stays quiet.
    """

    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    def color(self, name: str, fallback: int) -> int:
        colors = getattr(self.bot, "colors", None) or {}
        return colors.get(name, fallback)

    def is_target_guild(self, guild) -> bool:
        guild_id = config_get(self.bot, "guild_id")

        if guild_id is None:
            return True

        try:
            return int(getattr(guild, "id", 0)) == int(guild_id)
        except (TypeError, ValueError):
            return True

    def target_guild(self):
        guild_id = config_get(self.bot, "guild_id")

        if guild_id is None or not hasattr(self.bot, "get_guild"):
            return None

        try:
            return self.bot.get_guild(int(guild_id))
        except (TypeError, ValueError):
            return None

    def ignored_role_ids(self) -> set[int]:
        return config_id_set(self.bot, IGNORED_ROLES_KEY)

    def ignored_channel_ids(self) -> set[int]:
        return config_id_set(self.bot, IGNORED_CHANNELS_KEY)

    def build_embed(
        self,
        title: str,
        *,
        color_name: str = "blue",
        fallback: int = 0x5865F2,
        description: Optional[str] = None,
    ) -> nextcord.Embed:
        embed = nextcord.Embed(
            title=title,
            color=self.color(color_name, fallback),
            timestamp=datetime.now(timezone.utc),
        )

        if description:
            embed.description = clip(description, DESCRIPTION_LIMIT)

        return embed

    def set_author(self, embed: nextcord.Embed, user) -> None:
        if user is None:
            return

        name = getattr(user, "display_name", None) or getattr(user, "name", None) or str(user)
        avatar = getattr(user, "display_avatar", None) or getattr(user, "avatar", None)
        icon_url = getattr(avatar, "url", None)

        if icon_url:
            embed.set_author(name=name, icon_url=icon_url)
        else:
            embed.set_author(name=name)

    def add_actor(self, embed: nextcord.Embed, entry, *, name: str = "Performed By") -> None:
        """Adds the responsible moderator and their reason, when known."""
        actor = getattr(entry, "user", None) if entry is not None else None

        embed.add_field(
            name=name,
            value=format_user(actor) if actor is not None else "Unknown *(no audit log entry found)*",
            inline=True,
        )

        reason = getattr(entry, "reason", None) if entry is not None else None

        if reason:
            embed.add_field(name="Reason", value=clip(str(reason)), inline=False)

    async def audit(self, guild, action, **kwargs):
        return await find_audit_entry(guild, action, **kwargs)

    async def send_log(self, guild, embed: nextcord.Embed) -> None:
        if not self.is_target_guild(guild):
            return

        channel = resolve_log_channel(self.bot, guild)

        if channel is None:
            return

        try:
            await channel.send(
                embed=embed,
                allowed_mentions=nextcord.AllowedMentions.none(),
            )
        except Exception as exc:
            print(f"[ServerLog] Failed to send log embed: {type(exc).__name__}: {exc}")
