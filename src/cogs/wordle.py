import re
from datetime import datetime, timezone

import nextcord
from nextcord import Embed, Interaction, SlashOption, slash_command
from nextcord.ext import commands

from app_config import get_command_guild_ids, load_optional_config
from bot_base import APBot

conf = load_optional_config()
COMMAND_GUILD_IDS = get_command_guild_ids(conf)

WORDLE_RESULT_RE = re.compile(r"Wordle\s+(\d[\d,]*)\s+([1-6X])/6(\*)?", re.IGNORECASE)


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_wordle_result(content: str):
    match = WORDLE_RESULT_RE.search(content)
    if not match:
        return None

    puzzle = int(match.group(1).replace(",", ""))
    tries_text = match.group(2)
    hard_mode = bool(match.group(3))

    failed = tries_text.upper() == "X"
    tries = None if failed else int(tries_text)
    score = 7 if failed else tries - 1 if hard_mode else tries

    return {
        "puzzle": puzzle,
        "tries": tries,
        "failed": failed,
        "hard_mode": hard_mode,
        "score": score,
    }


def is_wordle_summary_message(content: str) -> bool:
    text = content.lower()
    return "yesterday" in text and "result" in text


def format_wordle_leaderboard(rows):
    if not rows:
        return "No Wordle scores have been recorded yet."

    lines = []
    for index, row in enumerate(rows, start=1):
        user_id = row["user_id"]
        total = row["total_score"]
        games = row["games"]
        hard_games = row["hard_games"]
        failures = row["failures"]
        lines.append(
            f"{index}. <@{user_id}> — {total} pts over {games} game(s), {hard_games} hard, {failures} failed"
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

        start = parse_date(start_date)
        end = parse_date(end_date)

        if start is None or end is None:
            await inter.followup.send("Use dates in YYYY-MM-DD format.", ephemeral=True)
            return

        if end < start:
            await inter.followup.send("End date must be after start date.", ephemeral=True)
            return

        await self.bot.db.wordle.start_season(inter.guild.id, inter.channel.id, start.isoformat(), end.isoformat())

        processed = 0
        async for message in inter.channel.history(limit=50):
            if await self.process_wordle_result_message(message):
                processed += 1

        await inter.followup.send(
            f"Started Wordle season from `{start.isoformat()}` to `{end.isoformat()}`. Processed {processed} existing result(s).",
            ephemeral=True,
        )

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

        if getattr(message.channel, "name", None) != "wordle":
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
        )
        return True

    async def post_leaderboard(self, message: nextcord.Message) -> None:
        season = await self.bot.db.wordle.get_active_season(message.guild.id)
        if not season:
            return

        if season.get("last_summary_message_id") == message.id:
            return

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

        if message.guild and message.author.bot and getattr(message.channel, "name", None) == "wordle":
            if is_wordle_summary_message(message.content):
                await self.post_leaderboard(message)


def setup(bot: APBot):
    bot.add_cog(Wordle(bot))
