from typing import Optional

from nextcord import ButtonStyle, Interaction, TextChannel, slash_command, ui
from nextcord.ext import commands

from bot_base import APBot


class EventAnnouncement(ui.View):
    def __init__(self, bot: APBot):
        super().__init__()
        self.bot = bot

    @ui.button(label="Click here to be notified for future events!", style=ButtonStyle.gray)
    async def callback(self, button: ui.Button, inter: Interaction):
        """
        Give the "Lounge: Events" role to the interaction user.
        """

        role = await self.bot.fetch_role(self.bot.guild.id, self.bot.config.get("events_role_id"))
        if not role:
            return await inter.send("There appears to be a bug within me, please report this :)", ephemeral=True)

        await inter.user.add_roles(role)
        await inter.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class EventConfirm(ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    @ui.button(label="Confirm!", emoji="✅", style=ButtonStyle.green)
    async def confirm(self, button: ui.Button, inter: Interaction):
        self.value = True
        self.stop()

    @ui.button(label="Cancel", emoji="❌", style=ButtonStyle.grey)
    async def cancel(self, button: ui.Button, inter: Interaction):
        self.value = False
        self.stop()


class Events(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="eventannounce", description="Announce an event in the #events channel.")
    async def eventannounce(self, inter: Interaction):
        await inter.response.defer(ephemeral=True)
        resp = await inter.send("Validating authorization...", ephemeral=True)

        if self.bot.config.get("event_coordinator_role_id") not in [i.id for i in inter.user.roles]:
            return await resp.edit("You are not allowed to run that command!")

        view = EventConfirm()
        await resp.edit(
            "Please confirm that you would like to **ping the events role** in the events channel.", view=view
        )
        await view.wait()

        if view.value is None:
            return await resp.edit("Timed out.", view=None)
        elif not view.value:
            return await resp.edit("Cancelled.", view=None)

        event_role = await self.bot.fetch_role(self.bot.guild.id, self.bot.config.get("events_role_id"))
        event_channel: Optional[TextChannel] = await self.bot.fetch_channel(self.bot.config.get("events_channel_id"))
        if not event_channel or not event_role:
            return await resp.edit("Failed to get events role/channel.")

        await event_channel.send(event_role.mention, view=EventAnnouncement(self.bot))
        return await resp.edit("Done!", view=None)


def setup(bot: APBot):
    bot.add_cog(Events(bot))
