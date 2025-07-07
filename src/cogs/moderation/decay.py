import asyncio
from datetime import datetime, timedelta

import nextcord
from nextcord import Embed
from nextcord.ext import commands, tasks

from bot_base import APBot


class Decay(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot
        self.decay.start()

    @tasks.loop(hours=24)
    async def decay(self):
        now = datetime.utcnow()
        weekday = now.weekday()  # 0 = Monday

        channel = await self.bot.getch_channel(self.bot.config.get("bot_logs_channel"))
        if not channel:
            print("[DECAY] Log channel 'bot-logs' not found.")
            return

        # Check if decay already applied today
        last_decay = await self.bot.db.decay.get_last_decay_date()
        already_ran_today = last_decay and last_decay.date() == now.date()

        if weekday == 0:  # Monday
            if already_ran_today:
                status = "True"
                desc = "Decay already applied earlier today.\n"
                color = self.bot.colors.get("green", nextcord.Color.green())
            else:
                # Apply decay and record timestamp
                success = await self.bot.db.decay.remove_one_inf()
                if success:
                    await self.bot.db.decay.set_last_decay_date(now)
                    status = "True"
                    desc = "1 IP removed from members with > 0 IP.\n"
                    color = self.bot.colors.get("green", nextcord.Color.green())
                else:
                    status = "False"
                    desc = "Decay failed to apply.\n"
                    color = self.bot.colors.get("red", nextcord.Color.red())
        else:
            status = "False"
            desc = "Decay only applies on Mondays.\n"
            color = self.bot.colors.get("red", nextcord.Color.red())

        # Calculate next Monday at 6:00 AM UTC
        days_until_monday = (7 - now.weekday()) % 7
        days_until_monday = 7 if days_until_monday == 0 else days_until_monday
        next_monday = (now + timedelta(days=days_until_monday)).replace(hour=6, minute=0, second=0, microsecond=0)

        emb = Embed(
            title=f"Decay Status: {status}",
            description=(
                f"{desc}"
                f"Next decay at <t:{int(next_monday.timestamp())}:F> "
                f"<t:{int(next_monday.timestamp())}:R>"
            ),
            color=color
        )

        await channel.send(embed=emb)

    @decay.before_loop
    async def decay_before_loop(self):
        await self.bot.wait_until_ready()

        try:
            now = datetime.utcnow()
            weekday = now.weekday()
            channel = nextcord.utils.get(self.bot.get_all_channels(), name="bot-logs")
            if not channel:
                print("[DECAY] Log channel 'bot-logs' not found.")
                return

            last_decay = await self.bot.db.decay.get_last_decay_date()
            already_ran_today = last_decay and last_decay.date() == now.date()

            if weekday == 0 and not already_ran_today:
                success = await self.bot.db.decay.remove_one_inf()
                if success:
                    await self.bot.db.decay.set_last_decay_date(now)
                    status = "True"
                    desc = "1 IP removed from members with > 0 IP."
                    color = self.bot.colors.get("green", nextcord.Color.green())
                else:
                    status = "False"
                    desc = "Decay failed to apply."
                    color = self.bot.colors.get("red", nextcord.Color.red())
            else:
                status = "False"
                desc = "Decay only runs on Mondays or already ran today."
                color = self.bot.colors.get("red", nextcord.Color.red())

            # Calculate next Monday at 6:00 AM UTC
            days_until_monday = (7 - now.weekday()) % 7
            days_until_monday = 7 if days_until_monday == 0 else days_until_monday
            next_monday = (now + timedelta(days=days_until_monday)).replace(hour=6, minute=0, second=0, microsecond=0)

            emb = Embed(
                title=f"Decay Status: {status}",
                description=(
                    f"{desc}\n"
                    f"Next decay at <t:{int(next_monday.timestamp())}:F> "
                    f"<t:{int(next_monday.timestamp())}:R>"
                ),
                color=color
            )

            await channel.send(embed=emb)

        except Exception as e:
            print(f"[DECAY] Failed to initialize decay timing: {e}")


def setup(bot: APBot) -> None:
    bot.add_cog(Decay(bot))
