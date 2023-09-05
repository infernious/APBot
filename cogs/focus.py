import asyncio
import time

from bot_base import APBot
from discord import Interaction, Object, app_commands
from discord.ext import commands

from cogs.utils import convert_time


class Study(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    async def remove_study_role(self, user_id: int) -> None:
        try:
            user = await self.bot.getch_member(self.bot.guild_id, user_id)
            role = await self.bot.getch_role(self.bot.config.get("study_role_id"))
        except:
            return

        if not user or not role:
            return

        await user.remove_roles(role)

    @app_commands.command(name="study", description="Prevent yourself from viewing unhelpful channels.")
    async def study(self, interaction: Interaction, duration: str):
        """
        Gives member the study role to prevent distraction/procrastination.
            - Checks if time is greater than or equal to 10 minutes.
            - Gives study role to member.
            - Updates user document in the database collection with datetime to remove the study role.
        """

        seconds = await convert_time(duration)
        if seconds <= 600:
            raise app_commands.AppCommandError("Please choose a duration greater than 10 minutes.")

        study_role_id = self.bot.config.get("study_role_id")

        if study_role_id in interaction.user.roles:
            raise app_commands.CheckFailure(
                f"You already have the study role! It will be automatically removed at <t:{await self.bot.db.get_user_study_expiry(interaction.user.id)}>\nIf you wish to have it removed, please send a DM to <@{self.bot.user.id}>"
            )

        await interaction.user.add_roles(await self.bot.getch_role(study_role_id))
        study_expires_at = int(time.time()) + seconds

        await self.bot.db.set_user_study_expiry(interaction.user.id, study_expires_at)

        self.bot.loop.call_later(seconds, asyncio.create_task, self.remove_study_role(interaction.user.id))
        await interaction.response.send_message(
            f"The study role will be removed <t:{study_expires_at}:R> at <t:{study_expires_at}:f>.", ephemeral=True
        )

    @commands.Cog.listener("on_ready")
    async def _study_on_ready(self) -> None:
        students = await self.bot.db.get_all_study_students()

        for user_id, expires_at in students.items():
            seconds = int(time.time()) - expires_at
            if seconds <= 0:
                await self.remove_study_role(user_id)
            else:
                self.bot.loop.call_later(seconds, asyncio.create_task, self.remove_study_role(user_id))


async def setup(bot: APBot):
    await bot.add_cog(Study(bot), guilds=[Object(id=bot.guild_id)])
