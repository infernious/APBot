from __future__ import annotations

import traceback
from typing import Optional

import nextcord
from nextcord.ext import commands

from bot_base import APBot
from cogs.server_log.base import (
    ServerLogCog,
    clip,
    config_get,
    format_user,
)


# Root names of the moderator/manager commands APBot ships with. Override in
# config with `server_log_mod_commands` to add or trim entries.
DEFAULT_MOD_COMMANDS: frozenset[str] = frozenset(
    {
        "warn",
        "warnchannel",
        "warnings",
        "wm",
        "mute",
        "selfmute",
        "unmute",
        "kick",
        "ban",
        "force-ban",
        "unban",
        "note",
        "restrict",
        "editip",
        "userip",
        "update",
        "esclude",
        "appealbutton",
        "purge",
    }
)

# Discord application command option types that are not real arguments.
SUBCOMMAND_TYPES = {1, 2}

MENTION_OPTION_TYPES = {
    6: "@",   # USER
    7: "#",   # CHANNEL
    8: "@&",  # ROLE
}


def resolve_command_name(interaction) -> str:
    """Rebuilds the full command name, including subcommand groups."""
    data = getattr(interaction, "data", None) or {}
    parts: list[str] = []

    name = data.get("name")

    if name:
        parts.append(str(name))

    options = data.get("options") or []

    while options:
        option = options[0]

        if option.get("type") not in SUBCOMMAND_TYPES:
            break

        parts.append(str(option.get("name")))
        options = option.get("options") or []

    if parts:
        return " ".join(parts)

    command = getattr(interaction, "application_command", None)
    return getattr(command, "qualified_name", None) or getattr(command, "name", None) or "unknown"


def leaf_options(interaction) -> list[dict]:
    data = getattr(interaction, "data", None) or {}
    options = data.get("options") or []

    while options and options[0].get("type") in SUBCOMMAND_TYPES:
        options = options[0].get("options") or []

    return [option for option in options if option.get("type") not in SUBCOMMAND_TYPES]


def format_option_value(option: dict) -> str:
    value = option.get("value")
    prefix = MENTION_OPTION_TYPES.get(option.get("type"))

    if prefix and value:
        return f"<{prefix}{value}>"

    if isinstance(value, bool):
        return "`Yes`" if value else "`No`"

    text = str(value)

    return f"`{clip(text, 300)}`" if text else "*empty*"


class ModCommandLog(ServerLogCog):
    """Logs every moderator/manager command that runs to completion."""

    def mod_commands(self) -> frozenset[str]:
        configured = config_get(self.bot, "server_log_mod_commands")

        if not configured:
            return DEFAULT_MOD_COMMANDS

        try:
            return frozenset(str(name).lower() for name in configured)
        except TypeError:
            return DEFAULT_MOD_COMMANDS

    def is_mod_command(self, full_name: str) -> bool:
        if not full_name:
            return False

        names = self.mod_commands()
        lowered = full_name.lower()

        # Match the root name so subcommands like `bonk purge` are caught too.
        return lowered in names or lowered.split(" ")[0] in names

    @commands.Cog.listener()
    async def on_application_command_completion(self, interaction: nextcord.Interaction) -> None:
        try:
            guild = getattr(interaction, "guild", None)

            if guild is None:
                return

            full_name = resolve_command_name(interaction)

            if not self.is_mod_command(full_name):
                return

            embed = self._build_embed(
                invoker=getattr(interaction, "user", None),
                guild=guild,
                channel=getattr(interaction, "channel", None),
                full_name=full_name,
                usage=self._format_slash_usage(full_name, interaction),
            )

            await self.send_log(guild, embed)

        except Exception as exc:
            print(f"[ServerLog] slash mod command logging failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        try:
            guild = getattr(ctx, "guild", None)

            if guild is None or ctx.command is None:
                return

            full_name = getattr(ctx.command, "qualified_name", None) or ctx.command.name

            if not self.is_mod_command(full_name):
                return

            content = getattr(getattr(ctx, "message", None), "content", "") or ""

            embed = self._build_embed(
                invoker=getattr(ctx, "author", None),
                guild=guild,
                channel=getattr(ctx, "channel", None),
                full_name=full_name,
                usage=f"`{clip(content, 900)}`" if content else f"`{full_name}`",
            )

            await self.send_log(guild, embed)

        except Exception as exc:
            print(f"[ServerLog] prefix mod command logging failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    def _format_slash_usage(self, full_name: str, interaction) -> str:
        options = leaf_options(interaction)

        if not options:
            return f"`/{full_name}`"

        rendered = " ".join(
            f"**{option.get('name')}:** {format_option_value(option)}" for option in options
        )

        return clip(f"`/{full_name}`\n{rendered}")

    def _build_embed(self, *, invoker, guild, channel, full_name: str, usage: str) -> nextcord.Embed:
        channel_mention = getattr(channel, "mention", None) or "Unknown channel"

        embed = self.build_embed(
            "Moderator Command Used",
            color_name="blue",
            fallback=0x3498DB,
            description=(
                f"{getattr(invoker, 'mention', 'Unknown')} ran a moderator command in {channel_mention}."
            ),
        )
        self.set_author(embed, invoker)
        embed.add_field(name="Moderator", value=format_user(invoker), inline=True)
        embed.add_field(name="Command", value=f"`{clip(full_name, 200)}`", inline=True)
        embed.add_field(name="Usage", value=usage, inline=False)
        embed.set_footer(text=f"Moderator ID: {getattr(invoker, 'id', 'unknown')}")

        return embed


def setup(bot: APBot) -> None:
    bot.add_cog(ModCommandLog(bot))
