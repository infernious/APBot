import nextcord
from nextcord import app_commands
from nextcord.ext import commands


blue = 0x00ffff


class EventAnnouncement(nextcord.ui.View):

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @nextcord.ui.button(label='Click here to be notified for future events!', style=nextcord.ButtonStyle.gray)
    async def callback(self, interaction, button):

        """
        Give the "Lounge: Events" role to the interaction user.
        """

        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Events")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class EventConfirm(nextcord.ui.View):

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @nextcord.ui.button(label='Confirm!', emoji='✅', style=nextcord.ButtonStyle.green)
    async def callback(self, interaction, button):

        """
        Confirm mention after command is used as to avoid accidental pings.
        """

        event_role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Events")
        event_channel = nextcord.utils.get(interaction.guild.channels, name="events")

        await event_channel.send(f"{event_role.mention}", view=EventAnnouncement(self.bot))

        button.style = nextcord.ButtonStyle.grey
        button.label = "Event announced!"
        button.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.message.delete()

        self.stop()


class Events(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.checks.has_role("Event Coordinator")
    @app_commands.command(name='eventannounce', description='Announce an event in the #events channel.')
    async def eventannounce(self, interaction: nextcord.Interaction):

        await interaction.response.send_message("Please confirm that you would like to **ping the events role** in the events channel.", view=EventConfirm(self.bot))


async def setup(bot):
    await bot.add_cog(Events(bot), guilds=[nextcord.Object(id=bot.guild_id)])