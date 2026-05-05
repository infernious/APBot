from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

import nextcord
from nextcord.ext import commands

from bot_base import APBot


LOG_CHANNEL_NAME = "leak-log"
LEAK_WORD_RE = re.compile(r"\bleak\b", re.IGNORECASE)


class LeakLog(commands.Cog):
    """Logs messages that contain the standalone keyword 'leak'."""

    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    def get_log_channel(self, guild: nextcord.Guild) -> Optional[nextcord.TextChannel]:
        channel = nextcord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        return channel if isinstance(channel, nextcord.TextChannel) else None

    def clip(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text

        return text[: limit - 20] + "\n... *(cut off)*"

    def contains_leak_word(self, content: str) -> bool:
        return LEAK_WORD_RE.search(content or "") is not None

    def safe_content(self, content: str) -> str:
        """Escape mentions and markdown so the log cannot ping or format unexpectedly."""
        content = content or ""
        content = nextcord.utils.escape_mentions(content)
        return nextcord.utils.escape_markdown(content)

    def highlighted_content(self, content: str) -> str:
        """Highlight standalone instances of 'leak' without using noisy emoji."""
        if not content:
            return "*No text content found.*"

        safe = self.safe_content(content)
        highlighted = LEAK_WORD_RE.sub(
            lambda match: f"**{match.group(0)}**",
            safe,
        )

        return self.clip(highlighted, 900)

    def quote_message_preview(self, content: str) -> str:
        highlighted = self.highlighted_content(content)
        lines = highlighted.splitlines() or [highlighted]
        quoted = "\n".join(f"> {line}" if line else ">" for line in lines)
        return self.clip(quoted, 1000)

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message) -> None:
        if message.guild is None:
            return

        if message.author.bot:
            return

        if not self.contains_leak_word(message.content or ""):
            return

        log_channel = self.get_log_channel(message.guild)

        if log_channel is None:
            return

        # Prevent logging messages from the log channel itself.
        if message.channel.id == log_channel.id:
            return

        embed = nextcord.Embed(
            title="Keyword Monitor Alert",
            description=(
                "A monitored keyword was detected in a server message.\n"
                f"[Jump to message]({message.jump_url})"
            ),
            color=self.bot.colors.get("yellow", nextcord.Color.gold()),
            timestamp=datetime.now(timezone.utc),
        )

        embed.set_author(
            name=str(message.author),
            icon_url=message.author.display_avatar.url,
        )

        embed.add_field(
            name="Keyword",
            value="`leak`",
            inline=True,
        )

        embed.add_field(
            name="Channel",
            value=message.channel.mention,
            inline=True,
        )

        embed.add_field(
            name="Message Preview",
            value=self.quote_message_preview(message.content or ""),
            inline=False,
        )

        embed.add_field(
            name="Author",
            value=f"{message.author.mention}\n`{message.author.id}`",
            inline=True,
        )

        embed.add_field(
            name="Message ID",
            value=f"`{message.id}`",
            inline=True,
        )

        embed.set_footer(text="Leak keyword monitor")

        await log_channel.send(
            embed=embed,
            allowed_mentions=nextcord.AllowedMentions.none(),
        )


async def setup(bot: APBot) -> None:
    bot.add_cog(LeakLog(bot))
