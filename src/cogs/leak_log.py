from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

import nextcord
from nextcord.ext import commands

from bot_base import APBot


LOG_CHANNEL_NAME = "leak-log"

MONITORED_KEYWORDS: tuple[str, ...] = (
    "leak",
    "leaks",
    "leaked",
    "leaking",
    "l3ak",
    "l3aks",
    "le@k",
    "le@ks",
    "|eak",
    "l e a k",
    "leek",
    "leeks",
    "cheat",
    "cheats",
    "cheating",
    "cheated",
    "ch3at",
    "ch3ats",
    "cheeting",
    "cheater",
    "c h e a t",
    "ch3ating",
    "form o",
    "form 0",
    "f0rm o",
    "form-o",
    "form-0",
    "form d",
    "form e",
    "unreleased",
    "un-released",
    "unreleasd",
    "test bank",
    "testbank",
    "exam bank",
    "exambank",
    "intl",
    "international",
    "intl form",
    "international exam",
    "form i",
    "form-i",
    "f0rm i",
    "late exam",
    "late testing",
    "late form",
    "makeup exam",
    "make up exam",
    "alternate form",
    "answer key",
    "ans key",
    "answrs",
    "ansr key",
    "mcq",
    "mcqs",
    "m.c.q",
    "multiple choice",
    "frq",
    "frqs",
    "f.r.q",
    "free response",
    "mcq answers",
    "frq answers",
    "sell",
    "selling",
    "s3ll",
    "s3lling",
    "$ell",
    "$elling",
    "buy",
    "buying",
    "buyin",
    "b u y",
    "cashapp",
    "cash app",
    "venmo",
    "paypal",
    "crypto",
    "btc",
    "dm for",
    "pm for",
    "dm me",
    "pm me",
    "message me for",
    "price",
    "prices",
)

# Boundaries prevent matching inside unrelated words, while still allowing
# terms that start with symbols, such as "$ell" and "|eak".
TEXT_LEFT_BOUNDARY = r"(?<![A-Za-z0-9_])"
TEXT_RIGHT_BOUNDARY = r"(?![A-Za-z0-9_])"


def keyword_to_regex(keyword: str) -> str:
    """
    Escapes a monitored keyword and makes spaces flexible.

    Example:
    - "test bank" matches "test bank" with any whitespace between words.
    - "form-o" stays hyphen-specific.
    - "$ell" and "|eak" stay symbol-specific.
    """
    escaped = re.escape(keyword)
    escaped = escaped.replace(r"\ ", r"\s+")
    return rf"{TEXT_LEFT_BOUNDARY}{escaped}{TEXT_RIGHT_BOUNDARY}"


KEYWORD_RE = re.compile(
    "|".join(
        keyword_to_regex(keyword)
        for keyword in sorted(MONITORED_KEYWORDS, key=len, reverse=True)
    ),
    re.IGNORECASE,
)


class LeakLog(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    def get_log_channel(self, guild: nextcord.Guild) -> Optional[nextcord.TextChannel]:
        channel = nextcord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
        return channel if isinstance(channel, nextcord.TextChannel) else None

    def clip(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text

        return text[: limit - 20] + "\n... *(cut off)*"

    def escape_for_embed(self, text: str) -> str:
        safe_text = nextcord.utils.escape_mentions(text)
        return nextcord.utils.escape_markdown(safe_text)

    def contains_monitored_keyword(self, content: str) -> bool:
        return KEYWORD_RE.search(content or "") is not None

    def detected_keywords(self, content: str) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()

        for match in KEYWORD_RE.finditer(content or ""):
            keyword = " ".join(match.group(0).lower().split())

            if keyword not in seen:
                seen.add(keyword)
                found.append(match.group(0))

        return found

    def highlighted_content(self, content: str) -> str:
        """
        Escapes Discord markdown/mentions, then highlights each matched term
        with simple bold formatting.
        """
        if not content:
            return "*No text content found.*"

        pieces: list[str] = []
        cursor = 0

        for match in KEYWORD_RE.finditer(content):
            pieces.append(self.escape_for_embed(content[cursor:match.start()]))
            pieces.append(f"**{self.escape_for_embed(match.group(0))}**")
            cursor = match.end()

        pieces.append(self.escape_for_embed(content[cursor:]))

        highlighted = "".join(pieces).strip()

        if not highlighted:
            return "*No text content found.*"

        return self.clip(highlighted, 950)

    def message_preview(self, content: str) -> str:
        highlighted = self.highlighted_content(content)
        quoted = "\n".join(f"> {line}" if line else ">" for line in highlighted.splitlines())
        return self.clip(quoted, 1000)

    def format_keyword_list(self, keywords: list[str]) -> str:
        if not keywords:
            return "Unknown"

        safe_keywords = [f"`{self.escape_for_embed(keyword)}`" for keyword in keywords[:10]]
        text = ", ".join(safe_keywords)

        if len(keywords) > 10:
            text += f", +{len(keywords) - 10} more"

        return self.clip(text, 1000)

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message) -> None:
        if message.guild is None:
            return

        if message.author.bot:
            return

        if not self.contains_monitored_keyword(message.content or ""):
            return

        log_channel = self.get_log_channel(message.guild)

        if log_channel is None:
            return

        # Prevent the logger from logging messages inside the log channel.
        if message.channel.id == log_channel.id:
            return

        keywords = self.detected_keywords(message.content or "")

        embed = nextcord.Embed(
            title="Keyword Monitor Alert",
            description=(
                f"A monitored keyword was detected in {message.channel.mention}. "
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
            name="Detected Keyword(s)",
            value=self.format_keyword_list(keywords),
            inline=False,
        )

        embed.add_field(
            name="Message Preview",
            value=self.message_preview(message.content or ""),
            inline=False,
        )

        embed.add_field(
            name="Author",
            value=f"{message.author.mention}\n`{message.author.id}`",
            inline=True,
        )

        embed.add_field(
            name="Channel",
            value=f"{message.channel.mention}\n`{message.channel.id}`",
            inline=True,
        )

        embed.add_field(
            name="Message ID",
            value=f"`{message.id}`",
            inline=True,
        )

        embed.set_footer(text="Keyword monitoring")

        await log_channel.send(
            embed=embed,
            allowed_mentions=nextcord.AllowedMentions.none(),
        )


def setup(bot: APBot) -> None:
    bot.add_cog(LeakLog(bot))
