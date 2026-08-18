from __future__ import annotations

import traceback

import nextcord
from nextcord.ext import commands

from bot_base import APBot
from cogs.server_log.base import ServerLogCog


def emoji_map(emojis) -> dict[int, nextcord.Emoji]:
    return {emoji.id: emoji for emoji in emojis or []}


def emoji_reference(emoji: nextcord.Emoji) -> str:
    kind = "Animated" if getattr(emoji, "animated", False) else "Static"
    return f"`:{emoji.name}:` (`{emoji.id}`)\n`{kind}`"


class EmojiLog(ServerLogCog):
    """Emoji Create / Name Change / Delete logs."""

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: nextcord.Guild, before, after) -> None:
        try:
            before_map = emoji_map(before)
            after_map = emoji_map(after)

            for emoji_id, emoji in after_map.items():
                if emoji_id not in before_map:
                    await self._log_created(guild, emoji)

            for emoji_id, emoji in before_map.items():
                if emoji_id not in after_map:
                    await self._log_deleted(guild, emoji)
                    continue

                if emoji.name != after_map[emoji_id].name:
                    await self._log_renamed(guild, emoji, after_map[emoji_id])

        except Exception as exc:
            print(f"[ServerLog] on_guild_emojis_update failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    async def _log_created(self, guild: nextcord.Guild, emoji: nextcord.Emoji) -> None:
        entry = await self.audit(
            guild,
            nextcord.AuditLogAction.emoji_create,
            target_id=emoji.id,
        )

        embed = self.build_embed(
            "Emoji Created",
            color_name="green",
            fallback=0x2ECC71,
            description=f"{emoji} `:{emoji.name}:` was added to the server.",
        )
        embed.add_field(name="Emoji", value=emoji_reference(emoji), inline=True)

        if getattr(emoji, "url", None):
            embed.set_thumbnail(url=emoji.url)

        self.add_actor(embed, entry, name="Created By")
        embed.set_footer(text=f"Emoji ID: {emoji.id}")

        await self.send_log(guild, embed)

    async def _log_deleted(self, guild: nextcord.Guild, emoji: nextcord.Emoji) -> None:
        entry = await self.audit(
            guild,
            nextcord.AuditLogAction.emoji_delete,
            target_id=emoji.id,
        )

        embed = self.build_embed(
            "Emoji Deleted",
            color_name="red",
            fallback=0xE74C3C,
            description=f"`:{emoji.name}:` was removed from the server.",
        )
        embed.add_field(name="Emoji", value=emoji_reference(emoji), inline=True)

        # The CDN URL still resolves right after deletion, so the preview works.
        if getattr(emoji, "url", None):
            embed.set_thumbnail(url=emoji.url)

        self.add_actor(embed, entry, name="Deleted By")
        embed.set_footer(text=f"Emoji ID: {emoji.id}")

        await self.send_log(guild, embed)

    async def _log_renamed(self, guild: nextcord.Guild, before: nextcord.Emoji, after: nextcord.Emoji) -> None:
        entry = await self.audit(
            guild,
            nextcord.AuditLogAction.emoji_update,
            target_id=after.id,
        )

        embed = self.build_embed(
            "Emoji Renamed",
            color_name="yellow",
            fallback=0xF1C40F,
            description=f"{after} was renamed.",
        )
        embed.add_field(name="Before", value=f"`:{before.name}:`", inline=True)
        embed.add_field(name="After", value=f"`:{after.name}:`", inline=True)

        if getattr(after, "url", None):
            embed.set_thumbnail(url=after.url)

        self.add_actor(embed, entry, name="Renamed By")
        embed.set_footer(text=f"Emoji ID: {after.id}")

        await self.send_log(guild, embed)


def setup(bot: APBot) -> None:
    bot.add_cog(EmojiLog(bot))
