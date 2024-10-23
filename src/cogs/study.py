import asyncio
import time
import nextcord
from typing import Union

from nextcord import Interaction, SlashOption, slash_command
from nextcord.ext import commands

from bot_base import APBot
from cogs.utils import convert_time


class Study(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    async def remove_study_role(self, user_id: int) -> None:
        try:
            user = await self.bot.getch_member(self.bot.guild.id, user_id)
            role = await self.bot.getch_role(self.bot.guild.id, self.bot.config.get("study_role_id"))
        except:
            return

        if not user or not role:
            return

        await self.bot.db.study.delete_user(user_id)
        await user.remove_roles(role)
    

    @slash_command(name="study", description="Prevent yourself from viewing unhelpful channels.")
    async def study(
        self,
        inter: Interaction,
        duration: str = SlashOption("duration", description="Reminder duration. Format: 5h9m2s", required=True),
    ):
        """
        Gives member the study role to prevent distraction/procrastination.
            - Checks if time is greater than or equal to 10 minutes.
            - Gives study role to member.
            - Updates user document in the database collection with datetime to remove the study role.
        """
        await inter.response.defer(ephemeral=True)

        resp = await inter.send("Validating time input...", ephemeral=True)

        duration: Union[str, int] = convert_time(duration)
        if isinstance(duration, str):
            return await resp.edit(content=duration)

        if duration < 60 * 10:
            return await resp.edit("Please set a duration greater than 10 minutes!")
        if duration > 60 * 60 * 24 * 7:
            return await resp.edit("Please set a duration lesser than a week")

        await resp.edit("Performing actions...")
        study_end = int(time.time()) + duration

        study_role_id = self.bot.config.get("study_role_id")

        if study_role_id in [i.id for i in inter.user.roles]:
            await resp.edit("Removing role...")
            await self.remove_study_role(inter.user.id)

        await inter.user.add_roles(await self.bot.getch_role(self.bot.guild.id, study_role_id))
        await resp.edit("Updating database...")

        await self.bot.db.study.set_time(inter.user.id, study_end)

        self.bot.loop.call_later(duration, asyncio.create_task, self.remove_study_role(inter.user.id))
        await resp.edit(
            f"The study role will be removed <t:{study_end}:R> at <t:{study_end}:f>."
        )
    
    class ConfirmDeny(nextcord.ui.View):
        def __init__(self) -> None:
            super().__init__(timeout=30)
            self.value = None

        @nextcord.ui.button(label = 'Yes', style=nextcord.ButtonStyle.green)
        async def remove_role(self, button: nextcord.ui.Button, inter: nextcord.Interaction):
            self.value = True
            self.stop()

        @nextcord.ui.button(label = 'No', style=nextcord.ButtonStyle.red)
        async def dont_remove_role(self, button: nextcord.ui.Button, inter: nextcord.Interaction):
            self.value = False
            self.stop()

    @slash_command(name="remove_study_role", description="Allow yourself to view channels once again (remove study role).")
    async def remove_study(
        self,
        inter: Interaction
    ):
        """
        Allow member to remove their study role (if they have it) if they are done with their studying.
            - Checks first if study role is at all present.
                - If present, proceed:
                    - Asks user to confirm the removal of the study role.
                    - If yes:
                        - Removes study role from member.
                        - Remove member's entry from database.
                        - Allows them to access all channels once again.
                    - If no, does nothing.
                    - If button view times out, does nothing as well.
                - If not, do nothing.
        """

        await inter.response.defer(ephemeral=True)
        
        study_role_id = self.bot.config.get("study_role_id")

        if study_role_id not in [i.id for i in inter.user.roles]:
            return await inter.followup.send("You do not have a study role to remove!")

        view = self.ConfirmDeny()

        resp = await inter.send("Are you sure you want to remove your study role early?", ephemeral=True, view=view)

        await view.wait()

        if view.value:
            await resp.edit("Removing role...", view=None)
            await self.remove_study_role(inter.user.id)
            return await resp.edit("Successfully removed role! You now have access to channels again.", view=None)
        return await resp.edit("Request cancelled.", view=None)
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        students = await self.bot.db.study.get_all()
        for user_id, expires_at in students.items():
            seconds = expires_at - int(time.time())
            if seconds <= 0:
                await self.remove_study_role(user_id)
            else:
                self.bot.loop.call_later(seconds, asyncio.create_task, self.remove_study_role(user_id))


def setup(bot: APBot):
    bot.add_cog(Study(bot))
