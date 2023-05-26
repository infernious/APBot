import discord
from discord import Button, Interaction, Object, app_commands
from discord.ext import commands

from bot_base import APBot


class EventAnnouncement(discord.ui.View):
    def __init__(self, bot: APBot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label="Click here to be notified for future events!", style=discord.ButtonStyle.gray)
    async def callback(self, interaction: Interaction, button):
        """
        Give the "Lounge: Events" role to the interaction user.
        """

        role = await self.bot.getch_role(interaction.guild.id, self.bot.config.get("events_role_id"))
        member = interaction.guild.get_member(interaction.user.id)

        if not member:
            await interaction.response.send_message("You must be in the server to use this command.", ephemeral=True)
            return

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class EventConfirm(discord.ui.View):
    def __init__(self, bot: APBot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label="Confirm!", emoji="✅", style=discord.ButtonStyle.green)
    async def callback(self, interaction: Interaction, button: Button):
        """
        Confirm mention after command is used as to avoid accidental pings.
        """

        event_role = await self.bot.getch_role(interaction.guild.id, self.bot.config.get("events_role_id"))
        event_channel = await self.bot.getch_channel(interaction.guild.id, self.bot.config.get("events_channel_id"))

        await event_channel.send(event_role.mention, view=EventAnnouncement(self.bot))

        button.style = discord.ButtonStyle.grey
        button.label = "Event announced!"
        button.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.message.delete()

        self.stop()


class Events(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @app_commands.checks.has_role("Event Coordinator")
    @app_commands.command(name="eventannounce", description="Announce an event in the #events channel.")
    async def eventannounce(self, interaction: Interaction):
        await interaction.response.send_message(
            "Please confirm that you would like to **ping the events role** in the events channel.", view=EventConfirm(self.bot)
        )


async def setup(bot: APBot):
    await bot.add_cog(Events(bot), guilds=[Object(id=bot.guild_id)])
