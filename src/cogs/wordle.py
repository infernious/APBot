import asyncio
import re
from datetime import datetime, timedelta, timezone

import nextcord
from nextcord import Embed, Interaction, SlashOption, slash_command
from nextcord.ext import commands

from app_config import get_command_guild_ids, load_optional_config
from bot_base import APBot

conf = load_optional_config()
COMMAND_GUILD_IDS = get_command_guild_ids(conf)

WORDLE_RESULT_RE = re.compile(r"\bWordle\s+(\d[\d,]*)\s+([1-6X])/6(\*)?", re.IGNORECASE)
WORDLE_SUMMARY_RE = re.compile(r"([1-6X])/6(\*)?\s*[:\-]\s*((?:<@!?\d+>\s*)+)", re.IGNORECASE)
MENTION_RE = re.compile(r"<@!?(\d+)>")


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None



def can_manage_wordle(member) -> bool:
    owner_ids = conf.get("owner_ids") or []
    if getattr(member, "id", None) in owner_ids:
        return True

    perms = getattr(member, "guild_permissions", None)
    if perms and (perms.manage_guild or perms.administrator):
        return True

    allowed_role_names = {"Trial Chat Moderator", "Chat Moderator", "Admin"}
    allowed_role_ids = {
        role_id
        for role_id in (
            conf.get("bot_staff_role_id"),
            conf.get("special_perms_role_id"),
        )
        if role_id is not None
    }

    return any(role.name in allowed_role_names or role.id in allowed_role_ids for role in getattr(member, "roles", []))


def is_wordle_channel(channel) -> bool:
    return (getattr(channel, "name", "") or "").lower() == "wordle"


def get_history_bounds(start, end):
    after = datetime(start.year, start.month, start.day, tzinfo=timezone.utc) - timedelta(seconds=1)
    end_plus_two = end + timedelta(days=2)
    before = datetime(end_plus_two.year, end_plus_two.month, end_plus_two.day, tzinfo=timezone.utc)
    return after, before


def wordle_score(tries, failed: bool, hard_mode: bool) -> int:
    if failed:
        return 7
    if hard_mode:
        return tries - 1
    return tries


def parse_wordle_result(content: str):
    match = WORDLE_RESULT_RE.search(content)
    if not match:
        return None

    puzzle = int(match.group(1).replace(",", ""))
    tries_text = match.group(2)
    hard_mode = bool(match.group(3))
    failed = tries_text.upper() == "X"
    tries = None if failed else int(tries_text)

    return {
        "puzzle": puzzle,
        "tries": tries,
        "failed": failed,
        "hard_mode": hard_mode,
        "score": wordle_score(tries, failed, hard_mode),
    }


def parse_wordle_summary_text(content: str):
    entries = []

    for match in WORDLE_SUMMARY_RE.finditer(content):
        tries_text = match.group(1)
        hard_mode = bool(match.group(2))
        mention_text = match.group(3)
        failed = tries_text.upper() == "X"
        tries = None if failed else int(tries_text)

        for user_id in MENTION_RE.findall(mention_text):
            entries.append({
                "user_id": int(user_id),
                "tries": tries,
                "failed": failed,
                "hard_mode": hard_mode,
                "score": wordle_score(tries, failed, hard_mode),
            })

    return entries


def is_wordle_summary_message(content: str) -> bool:
    text = content.lower()
    return (
        ("yesterday" in text and "result" in text)
        or "finished game of wordle" in text
        or "finished games of wordle" in text
        or bool(parse_wordle_summary_text(content))
    )


def get_message_text(message: nextcord.Message) -> str:
    parts = [message.content or ""]

    for embed in message.embeds:
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
        for field in embed.fields:
            if field.name:
                parts.append(field.name)
            if field.value:
                parts.append(field.value)
        if embed.footer and embed.footer.text:
            parts.append(embed.footer.text)

    return "\n".join(parts)


def format_wordle_leaderboard(rows):
    if not rows:
        return "No Wordle scores have been recorded yet."

    lines = []
    for index, row in enumerate(rows, start=1):
        lines.append(
            f'{index}. <@{row["user_id"]}> — {row["total_score"]} pts over {row["games"]} game(s), {row["hard_games"]} hard, {row["failures"]} failed'
        )

    return "\n".join(lines)


class Wordle(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="wordle", description="Manage the Wordle leaderboard", guild_ids=COMMAND_GUILD_IDS)
    async def wordle(self, inter: Interaction):
        pass

    @wordle.subcommand(name="start", description="Start a seasonal Wordle leaderboard")
    async def wordle_start(
        self,
        inter: Interaction,
        start_date: str = SlashOption(name="start_date", description="YYYY-MM-DD", required=True),
        end_date: str = SlashOption(name="end_date", description="YYYY-MM-DD", required=True),
    ) -> None:
        await inter.response.defer(ephemeral=True)

        if not can_manage_wordle(inter.user):
            await inter.followup.send("Only staff can start Wordle seasons.", ephemeral=True)
            return

        if not is_wordle_channel(inter.channel):
            await inter.followup.send("Run this in #wordle.", ephemeral=True)
            return

        start = parse_date(start_date)
        end = parse_date(end_date)

        if start is None or end is None:
            await inter.followup.send("Use dates in YYYY-MM-DD format.", ephemeral=True)
            return

        if end < start:
            await inter.followup.send("End date must be after start date.", ephemeral=True)
            return

        await self.bot.db.wordle.start_season(inter.guild.id, inter.channel.id, start.isoformat(), end.isoformat())

        processed = await self.sync_channel_history(inter.channel, start, end)

        await inter.followup.send(
            f"Started Wordle season from `{start.isoformat()}` to `{end.isoformat()}`. Processed {processed} existing result(s).",
            ephemeral=True,
        )

    async def sync_channel_history(self, channel, start, end) -> int:
        after, before = get_history_bounds(start, end)
        processed = 0

        async for message in channel.history(limit=None, after=after, before=before, oldest_first=True):
            if await self.process_wordle_result_message(message):
                processed += 1
            processed += await self.process_wordle_summary_message(message)

        return processed

    @wordle.subcommand(name="sync", description="Sync past Wordle messages for the active season")
    async def wordle_sync(self, inter: Interaction) -> None:
        await inter.response.defer(ephemeral=True)

        if not can_manage_wordle(inter.user):
            await inter.followup.send("Only staff can sync Wordle seasons.", ephemeral=True)
            return

        if not is_wordle_channel(inter.channel):
            await inter.followup.send("Run this in #wordle.", ephemeral=True)
            return

        season = await self.bot.db.wordle.get_active_season(inter.guild.id)
        if not season:
            await inter.followup.send("No active Wordle season.", ephemeral=True)
            return

        start = parse_date(season["start_date"])
        end = parse_date(season["end_date"])
        processed = await self.sync_channel_history(inter.channel, start, end)

        await inter.followup.send(f"Synced {processed} Wordle result(s).", ephemeral=True)

    @wordle.subcommand(name="leaderboard", description="Show the active Wordle leaderboard")
    async def wordle_leaderboard(self, inter: Interaction) -> None:
        season = await self.bot.db.wordle.get_active_season(inter.guild.id)

        if not season:
            await inter.send("No active Wordle season.", ephemeral=True)
            return

        rows = await self.bot.db.wordle.get_leaderboard(
            inter.guild.id,
            season["start_date"],
            season["end_date"],
        )

        embed = Embed(
            title="Wordle Leaderboard",
            description=format_wordle_leaderboard(rows),
            color=self.bot.colors.get("green", nextcord.Color.green()),
        )

        await inter.send(embed=embed)

    async def process_wordle_result_message(self, message: nextcord.Message) -> bool:
        if message.guild is None or message.author.bot:
            return False

        if not is_wordle_channel(message.channel):
            return False

        result = parse_wordle_result(message.content)
        if result is None:
            return False

        season = await self.bot.db.wordle.get_active_season(message.guild.id)
        if not season:
            return False

        played_date = message.created_at.astimezone(timezone.utc).date().isoformat()
        if played_date < season["start_date"] or played_date > season["end_date"]:
            return False

        await self.bot.db.wordle.save_result(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
            user_id=message.author.id,
            username=message.author.display_name,
            puzzle=result["puzzle"],
            tries=result["tries"],
            failed=result["failed"],
            hard_mode=result["hard_mode"],
            score=result["score"],
            played_date=played_date,
            message_id=message.id,
            season_start=season["start_date"],
            season_end=season["end_date"],
            source="user_share",
        )
        return True

    async def process_wordle_summary_message(self, message: nextcord.Message) -> int:
        if message.guild is None or not message.author.bot:
            return 0

        if not is_wordle_channel(message.channel):
            return 0

        text = get_message_text(message)
        entries = parse_wordle_summary_text(text)

        if not entries:
            return 0

        season = await self.bot.db.wordle.get_active_season(message.guild.id)
        if not season:
            return 0

        created_date = message.created_at.astimezone(timezone.utc).date()
        played_date = created_date - timedelta(days=1) if "yesterday" in text.lower() else created_date
        played_date_text = played_date.isoformat()

        if played_date_text < season["start_date"] or played_date_text > season["end_date"]:
            return 0

        count = 0
        for entry in entries:
            member = message.guild.get_member(entry["user_id"])
            username = member.display_name if member else str(entry["user_id"])

            await self.bot.db.wordle.save_result(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                user_id=entry["user_id"],
                username=username,
                puzzle=None,
                tries=entry["tries"],
                failed=entry["failed"],
                hard_mode=entry["hard_mode"],
                score=entry["score"],
                played_date=played_date_text,
                message_id=message.id,
                season_start=season["start_date"],
                season_end=season["end_date"],
                source="wordle_bot_summary",
            )
            count += 1

        return count

    async def post_leaderboard(self, message: nextcord.Message) -> None:
        season = await self.bot.db.wordle.get_active_season(message.guild.id)
        if not season:
            return

        if season.get("last_summary_message_id") == message.id:
            return

        await self.process_wordle_summary_message(message)

        async for recent_message in message.channel.history(limit=100):
            await self.process_wordle_result_message(recent_message)

        rows = await self.bot.db.wordle.get_leaderboard(
            message.guild.id,
            season["start_date"],
            season["end_date"],
        )

        embed = Embed(
            title="Updated Wordle Leaderboard",
            description=format_wordle_leaderboard(rows),
            color=self.bot.colors.get("green", nextcord.Color.green()),
        )

        await message.channel.send(embed=embed)
        await self.bot.db.wordle.set_last_summary_message(message.guild.id, message.id)

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message) -> None:
        await self.process_wordle_result_message(message)

        if message.guild and message.author.bot and is_wordle_channel(message.channel):
            if is_wordle_summary_message(get_message_text(message)):
                await asyncio.sleep(5)
                await self.post_leaderboard(message)


def setup(bot: APBot):
    bot.add_cog(Wordle(bot))
