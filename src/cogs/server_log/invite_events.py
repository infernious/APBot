from __future__ import annotations

import re
import traceback

import nextcord
from nextcord.ext import commands

from bot_base import APBot
from cogs.server_log.base import (
    ServerLogCog,
    clip,
    format_timestamp,
    format_user,
)


# Only official invite hosts are matched, since those are the ones the API can
# resolve into real invite info.
INVITE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:discord(?:app)?\.com/invite|discord\.gg)/([A-Za-z0-9\-_]{2,64})",
    re.IGNORECASE,
)

MAX_INVITES_PER_MESSAGE = 3


class InviteLog(ServerLogCog):
    """Logs the details of any Discord invite a member posts in the server."""

    def find_invite_codes(self, content: str) -> list[str]:
        codes: list[str] = []
        seen: set[str] = set()

        for match in INVITE_RE.finditer(content or ""):
            code = match.group(1)
            lowered = code.lower()

            if lowered not in seen:
                seen.add(lowered)
                codes.append(code)

        return codes[:MAX_INVITES_PER_MESSAGE]

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message) -> None:
        try:
            if message.guild is None or message.author.bot:
                return

            if message.channel.id in self.ignored_channel_ids():
                return

            codes = self.find_invite_codes(message.content or "")

            if not codes:
                return

            for code in codes:
                await self._log_invite(message, code)

        except Exception as exc:
            print(f"[ServerLog] invite logging failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    async def _log_invite(self, message: nextcord.Message, code: str) -> None:
        invite = None

        try:
            invite = await self.bot.fetch_invite(code, with_counts=True)
        except Exception:
            # Expired, revoked, or otherwise unresolvable — still worth logging.
            invite = None

        embed = self.build_embed(
            "Invite Posted",
            color_name="yellow",
            fallback=0xF1C40F,
            description=(
                f"{message.author.mention} posted an invite in {message.channel.mention} "
                f"[Jump to message]({message.jump_url})"
            ),
        )
        self.set_author(embed, message.author)
        embed.add_field(name="Posted By", value=format_user(message.author), inline=True)
        embed.add_field(name="Invite Code", value=f"`{clip(code, 200)}`", inline=True)

        if invite is None:
            embed.add_field(
                name="Invite Target",
                value="*Could not be resolved (invalid, expired, or revoked).*",
                inline=False,
            )
        else:
            target_guild = getattr(invite, "guild", None)
            guild_name = getattr(target_guild, "name", None) or "Unknown"
            guild_id = getattr(target_guild, "id", None)

            is_own_server = guild_id is not None and guild_id == getattr(message.guild, "id", None)

            embed.add_field(
                name="Invite Target",
                value=(
                    f"`{guild_name}` (`{guild_id if guild_id is not None else 'unknown'}`)"
                    + ("\n*This server*" if is_own_server else "")
                ),
                inline=False,
            )

            invite_channel = getattr(invite, "channel", None)

            if invite_channel is not None:
                embed.add_field(
                    name="Invite Channel",
                    value=f"`{getattr(invite_channel, 'name', 'unknown')}`",
                    inline=True,
                )

            inviter = getattr(invite, "inviter", None)

            if inviter is not None:
                embed.add_field(name="Created By", value=format_user(inviter), inline=True)

            member_count = getattr(invite, "approximate_member_count", None)
            online_count = getattr(invite, "approximate_presence_count", None)

            if member_count is not None:
                counts = f"`{member_count}` members"

                if online_count is not None:
                    counts += f" • `{online_count}` online"

                embed.add_field(name="Server Size", value=counts, inline=True)

            expires_at = getattr(invite, "expires_at", None)
            embed.add_field(
                name="Expires",
                value=format_timestamp(expires_at) if expires_at else "`Never`",
                inline=True,
            )

            icon = getattr(target_guild, "icon", None)
            icon_url = getattr(icon, "url", None)

            if icon_url:
                embed.set_thumbnail(url=icon_url)

        embed.set_footer(text=f"Author ID: {message.author.id} • Message ID: {message.id}")

        await self.send_log(message.guild, embed)


def setup(bot: APBot) -> None:
    bot.add_cog(InviteLog(bot))
