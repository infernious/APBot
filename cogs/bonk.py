import asyncio
import time

from bot_base import APBot
from discord import Embed, Interaction, Object, app_commands
from discord.ext import commands

from cogs.utils import convert_time


class Bonk(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    async def remind(self, bonk_details) -> None:
        user_id, end_time, message = bonk_details

        await self.bot.db.remove_bonk(user_id, end_time, message)
        user = await self.bot.getch_user(user_id)

        if not user:
            return

        await user.send(f"Reminder! Set on: <t:{end_time}:F>\n{message}")

    @app_commands.command(name="bonk", description="Set a reminder!")
    async def _bonk(self, interaction: Interaction, duration: str, *, message: str = None) -> None:
        duration = convert_time(duration)

        if duration > 60 * 60 * 24 * 7 * 52 * 4:
            raise app_commands.CheckFailure("You can't set a reminder for more than 4 years.")

        end_time = time.time() + duration
        await self.bot.db.set_reminder(interaction.user.id, end_time, message)

        self.bot.loop.call_later(
            duration,
            asyncio.create_task,
            self.remind(interaction.user.id, message),
        )

        m = f"about `{message}` " if message else ""
        await interaction.response.send_message(f"I'll remind you {m}on <t:{int(end_time)}:F>", ephemeral=True)

    @app_commands.command(name="bonks", description="List all your reminders")
    async def _bonks(self, interaction: Interaction) -> None:
        user_reminders = await self.bot.db.get_all_reminders(interaction.user.id)
        if len(user_reminders) == 0:
            return await interaction.response.send_message("You have no set reminders!", ephemeral=True)

        user_reminders = sorted(user_reminders, key=lambda x: x[0])

        await interaction.response.send_message(
            embed=Embed(
                title="Your Reminders",
                description="\n".join(
                    [
                        f"`{i+1}.` Set on: <t:{user_reminders[i][0]}:F> {user_reminders[i][1][:((2000 - ((31 * len(user_reminders)) - 2)) / len(user_reminders))-4]}..."
                        for i in range(len(user_reminders))
                    ]
                ),
            ),
            ephemeral=True,
        )

    @app_commands.command(name="bonkremove", description="Remove a specific reminder!")
    async def _remove_reminder(self, interaction: Interaction, index: int):
        user_reminders = await self.bot.db.get_all_user_reminders(interaction.user.id)
        if len(user_reminders) == 0:
            return await interaction.response.send_message("You have no set reminders!", ephemeral=True)

        user_reminders = sorted(user_reminders, key=lambda x: x[0])

        if index > len(user_reminders):
            return await interaction.response.send_message(
                "You don't have that many reminders! Use `/bonks` to get a list of all your reminders!"
            )

        await self.bot.db.remove_bonk(interaction.user.id, user_reminders[index - 1][0], user_reminders[index - 1][1])
        await interaction.response.send_message("Removed reminder.", ephemeral=True)

    @app_commands.command(name="bonkpurge", description="Remove all reminders")
    async def _remove_all_reminders(self, interaction: Interaction):
        await self.bot.db.remove_all_bonks(interaction.user.id)
        await interaction.response.send_message("Removed all reminders!", ephemeral=True)

    @commands.Cog.listener("on_ready")
    async def _bonk_on_ready(self) -> None:
        bonks = await self.bot.db.get_all_reminders()

        for bonk in bonks:
            time_left = time.time() - bonk[1]
            if time_left < 0:
                await self.remind(bonk)
            else:
                await self.bot.loop.call_later(time_left, asyncio.create_task, self.remind(bonk))


async def setup(bot: APBot):
    await bot.add_cog(Bonk(bot), guilds=[Object(id=bot.guild_id)])
