from __future__ import annotations

import traceback
from typing import Optional

import nextcord
from nextcord.ext import commands

from bot_base import APBot
from cogs.server_log.base import (
    ServerLogCog,
    clip,
    prettify_flag,
)


# Channel settings worth logging, as (attribute, label, formatter).
TRACKED_SETTINGS: tuple[tuple[str, str], ...] = (
    ("name", "Name"),
    ("topic", "Topic"),
    ("nsfw", "Age Restricted"),
    ("slowmode_delay", "Slowmode"),
    ("bitrate", "Bitrate"),
    ("user_limit", "User Limit"),
)


def channel_type_name(channel) -> str:
    channel_type = getattr(channel, "type", None)
    name = getattr(channel_type, "name", None) or str(channel_type or "unknown")
    return prettify_flag(name)


def category_name(channel) -> str:
    category = getattr(channel, "category", None)
    return f"`{category.name}`" if category is not None else "*None*"


def setting_value(channel, attribute: str) -> Optional[str]:
    value = getattr(channel, attribute, None)

    if value is None:
        return None

    if attribute == "slowmode_delay":
        return f"`{value}s`" if value else "`Off`"

    if attribute == "nsfw":
        return f"`{'Yes' if value else 'No'}`"

    if attribute == "topic":
        return clip(str(value), 400) if value else "*None*"

    return f"`{value}`"


def overwrite_state(overwrite) -> dict[str, Optional[bool]]:
    return {name: value for name, value in overwrite}


def state_symbol(value: Optional[bool]) -> str:
    if value is True:
        return "✅ Allow"

    if value is False:
        return "❌ Deny"

    return "➖ Inherit"


def overwrite_map(channel) -> dict[int, tuple[object, object]]:
    """Maps overwrite target id -> (target, overwrite) so before/after can be diffed."""
    result: dict[int, tuple[object, object]] = {}

    for target, overwrite in (getattr(channel, "overwrites", None) or {}).items():
        target_id = getattr(target, "id", None)

        if target_id is not None:
            result[target_id] = (target, overwrite)

    return result


def target_label(target) -> str:
    mention = getattr(target, "mention", None)
    name = getattr(target, "name", None) or "unknown"

    if mention:
        return f"{mention} (`{name}`)"

    return f"`{name}`"


def describe_overwrite(overwrite) -> str:
    lines = [
        f"`{prettify_flag(name)}`: {state_symbol(value)}"
        for name, value in sorted(overwrite_state(overwrite).items())
        if value is not None
    ]

    return clip("\n".join(lines)) if lines else "*No explicit permissions*"


def diff_overwrite(before_overwrite, after_overwrite) -> list[str]:
    before_state = overwrite_state(before_overwrite)
    after_state = overwrite_state(after_overwrite)

    lines: list[str] = []

    for name in sorted(set(before_state) | set(after_state)):
        old = before_state.get(name)
        new = after_state.get(name)

        if old != new:
            lines.append(f"`{prettify_flag(name)}`: {state_symbol(old)} → {state_symbol(new)}")

    return lines


class ChannelLog(ServerLogCog):
    """Channel Create / Delete / Update (settings and permission overwrites) logs."""

    def is_ignored(self, channel) -> bool:
        channel_id = getattr(channel, "id", None)
        return channel_id is not None and channel_id in self.ignored_channel_ids()

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel) -> None:
        try:
            if self.is_ignored(channel):
                return

            entry = await self.audit(
                channel.guild,
                nextcord.AuditLogAction.channel_create,
                target_id=channel.id,
            )

            embed = self.build_embed(
                "Channel Created",
                color_name="green",
                fallback=0x2ECC71,
                description=f"{getattr(channel, 'mention', channel.name)} was created.",
            )
            embed.add_field(name="Channel", value=f"`{channel.name}` (`{channel.id}`)", inline=True)
            embed.add_field(name="Type", value=f"`{channel_type_name(channel)}`", inline=True)
            embed.add_field(name="Category", value=category_name(channel), inline=True)
            self.add_actor(embed, entry, name="Created By")
            embed.set_footer(text=f"Channel ID: {channel.id}")

            await self.send_log(channel.guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_guild_channel_create failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel) -> None:
        try:
            if self.is_ignored(channel):
                return

            entry = await self.audit(
                channel.guild,
                nextcord.AuditLogAction.channel_delete,
                target_id=channel.id,
            )

            embed = self.build_embed(
                "Channel Deleted",
                color_name="red",
                fallback=0xE74C3C,
                description=f"**#{channel.name}** was deleted.",
            )
            embed.add_field(name="Channel", value=f"`{channel.name}` (`{channel.id}`)", inline=True)
            embed.add_field(name="Type", value=f"`{channel_type_name(channel)}`", inline=True)
            embed.add_field(name="Category", value=category_name(channel), inline=True)
            self.add_actor(embed, entry, name="Deleted By")
            embed.set_footer(text=f"Channel ID: {channel.id}")

            await self.send_log(channel.guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_guild_channel_delete failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after) -> None:
        try:
            if self.is_ignored(after):
                return

            setting_changes = self._setting_changes(before, after)
            permission_changes = self._permission_changes(before, after)

            # Position changes fire this event on every channel reorder; ignoring
            # them is what keeps the log readable.
            if not setting_changes and not permission_changes:
                return

            # Adding, editing and removing an overwrite are three different audit
            # actions, so scan unfiltered and accept whichever one shows up.
            candidate_actions = set()

            if setting_changes:
                candidate_actions.add(nextcord.AuditLogAction.channel_update)

            if permission_changes:
                candidate_actions.update(
                    {
                        nextcord.AuditLogAction.overwrite_create,
                        nextcord.AuditLogAction.overwrite_update,
                        nextcord.AuditLogAction.overwrite_delete,
                    }
                )

            entry = await self.audit(
                after.guild,
                None,
                target_id=after.id,
                limit=15,
                check=lambda candidate: getattr(candidate, "action", None) in candidate_actions,
            )

            embed = self.build_embed(
                "Channel Updated",
                color_name="yellow",
                fallback=0xF1C40F,
                description=f"{getattr(after, 'mention', after.name)} was updated.",
            )
            embed.add_field(name="Channel", value=f"`{after.name}` (`{after.id}`)", inline=False)

            for name, value in setting_changes:
                embed.add_field(name=name, value=clip(value), inline=False)

            for name, value in permission_changes:
                embed.add_field(name=name, value=clip(value), inline=False)

            self.add_actor(embed, entry, name="Updated By")
            embed.set_footer(text=f"Channel ID: {after.id}")

            await self.send_log(after.guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_guild_channel_update failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    def _setting_changes(self, before, after) -> list[tuple[str, str]]:
        changes: list[tuple[str, str]] = []

        for attribute, label in TRACKED_SETTINGS:
            if not hasattr(after, attribute):
                continue

            if getattr(before, attribute, None) == getattr(after, attribute, None):
                continue

            old = setting_value(before, attribute) or "*None*"
            new = setting_value(after, attribute) or "*None*"
            changes.append((label, f"{old} → {new}"))

        before_category = getattr(getattr(before, "category", None), "id", None)
        after_category = getattr(getattr(after, "category", None), "id", None)

        if before_category != after_category:
            changes.append(("Category", f"{category_name(before)} → {category_name(after)}"))

        return changes

    def _permission_changes(self, before, after) -> list[tuple[str, str]]:
        before_map = overwrite_map(before)
        after_map = overwrite_map(after)

        changes: list[tuple[str, str]] = []

        for target_id, (target, overwrite) in after_map.items():
            if target_id not in before_map:
                changes.append((
                    f"Permissions Added — {getattr(target, 'name', target_id)}",
                    f"{target_label(target)}\n{describe_overwrite(overwrite)}",
                ))
                continue

            lines = diff_overwrite(before_map[target_id][1], overwrite)

            if lines:
                changes.append((
                    f"Permissions Changed — {getattr(target, 'name', target_id)}",
                    f"{target_label(target)}\n" + "\n".join(lines),
                ))

        for target_id, (target, overwrite) in before_map.items():
            if target_id not in after_map:
                changes.append((
                    f"Permissions Removed — {getattr(target, 'name', target_id)}",
                    f"{target_label(target)}\n{describe_overwrite(overwrite)}",
                ))

        # Embeds cap at 25 fields; a mass permission sync can blow past that.
        if len(changes) > 8:
            hidden = len(changes) - 8
            changes = changes[:8]
            changes.append(("Note", f"+{hidden} more permission target(s) changed."))

        return changes


def setup(bot: APBot) -> None:
    bot.add_cog(ChannelLog(bot))
