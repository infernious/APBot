import discord
from discord import app_commands
from discord.ext import commands


blue = 0x00ffff


class EventAnnouncement(discord.ui.View):

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label='Click here to be notified for future events!', style=discord.ButtonStyle.gray)
    async def callback(self, interaction, button):

        """
        Give the "Lounge: Events" role to the interaction user.
        """

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Events")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class EventConfirm(discord.ui.View):

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @discord.ui.button(label='Confirm!', emoji='✅', style=discord.ButtonStyle.green)
    async def callback(self, interaction, button):

        """
        Confirm mention after command is used as to avoid accidental pings.
        """

        event_role = discord.utils.get(interaction.guild.roles, name="Lounge: Events")
        event_channel = discord.utils.get(interaction.guild.channels, name="events")

        await event_channel.send(f"{event_role.mention}", view=EventAnnouncement(self.bot))

        button.style = discord.ButtonStyle.grey
        button.label = "Event announced!"
        button.disabled = True

        await interaction.response.edit_message(view=self)

        self.stop()


class Events(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.checks.has_role("Event Coordinator")
    @app_commands.command(name='eventannounce', description='Announce an event in the #events channel.')
    async def eventannounce(self, interaction: discord.Interaction):

        await interaction.response.send_message("Please confirm that you would like to **ping the events role** in the events channel.", view=EventConfirm(self.bot))


async def setup(bot):
    await bot.add_cog(Events(bot), guilds=[discord.Object(id=bot.guild_id)])
