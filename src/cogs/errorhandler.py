from nextcord import Interaction, SlashOption, slash_command
from nextcord.ext import commands
from nextcord.utils import get

class Event(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def toggle_role(self, member, role_name: str) -> str:
        """
        Toggles the given role for the member.
        """
        role = get(member.guild.roles, name=role_name)
        if not role:
            return f"Role `{role_name}` not found."

        if role in member.roles:
            await member.remove_roles(role)
            return f"`{role.name}` role removed!"
        else:
            await member.add_roles(role)
            return f"`{role.name}` role added!"

    async def remove_role(self, member, role_name: str) -> str:
        """
        Removes the specified role from the member.
        """
        role = get(member.guild.roles, name=role_name)
        if not role:
            return f"Role `{role_name}` not found."
        
        if role in member.roles:
            await member.remove_roles(role)
            return f"`{role.name}` role removed!"
        else:
            return f"`{role_name}` role not found in your roles."

    @slash_command(name="event", description="Manage event notifications and announcements.")
    async def event(self, inter: Interaction):
        ...

    @event.subcommand(name="notify", description="Toggle notifications for events.")
    async def event_notify(self, inter: Interaction):
        """
        Toggle the 'Lounge: Events' role for the user.
        """
        response = await self.toggle_role(inter.user, "Lounge: Events")
        await inter.response.send_message(response, ephemeral=True)

    @event.subcommand(name="announce", description="Announce an event.")
    async def event_announce(self, inter: Interaction):
        """
        Announce an event.
        """
        event_role = get(inter.guild.roles, name="Lounge: Events")
        event_channel = get(inter.guild.channels, name="events")

        if not event_role or not event_channel:
            await inter.response.send_message(
                "Role or channel not found. Please contact an admin.",
                ephemeral=True,
            )
            return

        await event_channel.send(f"{event_role.mention}")
        await inter.response.send_message("Event announced!", ephemeral=True)

    @slash_command(name="qotd", description="Manage QOTD roles and announcements.")
    async def qotd(self, inter: Interaction):
        ...

    @qotd.subcommand(name="role", description="Toggle QOTD or QOTD-Poll role.")
    async def qotd_role(
        self,
        inter: Interaction,
        role_name: str = SlashOption(
            choices=["qotd", "qotd-poll"],
            description="Choose the role to toggle.",
        ),
    ):
        """
        Toggle the 'qotd' or 'qotd-poll' role for the user.
        """
        response = await self.toggle_role(inter.user, role_name)
        await inter.response.send_message(response, ephemeral=True)

    @qotd.subcommand(name="announce", description="Ping the QOTD role.")
    async def qotd_announce(self, inter: Interaction):
        """
        Ping the 'qotd' role in the 'qotd' channel.
        """
        # Check if the user has the Event Coordinator role
        event_coord_role = get(inter.guild.roles, name="Event Coordinator")
        if event_coord_role not in inter.user.roles:
            await inter.response.send_message(
                "You do not have the required role to use this command.",
                ephemeral=True,
            )
            return

        # Ensure the command is being run in the correct channel
        if inter.channel and inter.channel.name != "qotd":
            await inter.response.send_message(
                "This command can only be run in the 'qotd' channel.",
                ephemeral=True,
            )
            return

        qotd_role = get(inter.guild.roles, name="qotd")
        qotd_channel = get(inter.guild.channels, name="qotd")

        if not qotd_channel or not qotd_role:
            await inter.response.send_message(
                "Role or channel not found. Please contact an admin.",
                ephemeral=True,
            )
            return

        await qotd_channel.send(f"{qotd_role.mention}")
        await inter.response.send_message("QOTD announced!", ephemeral=True)

    @qotd.subcommand(name="poll", description="Ping the QOTD-Poll role.")
    async def qotd_poll(self, inter: Interaction):
        """
        Ping the 'qotd-poll' role in the 'qotd-poll' channel.
        """
        # Check if the user has the Event Coordinator role
        event_coord_role = get(inter.guild.roles, name="Event Coordinator")
        if event_coord_role not in inter.user.roles:
            await inter.response.send_message(
                "You do not have the required role to use this command.",
                ephemeral=True,
            )
            return

        # Ensure the command is being run in the correct channel
        if inter.channel and inter.channel.name != "qotd-poll":
            await inter.response.send_message(
                "This command can only be run in the 'qotd-poll' channel.",
                ephemeral=True,
            )
            return

        poll_role = get(inter.guild.roles, name="qotd-poll")
        poll_channel = get(inter.guild.channels, name="qotd-poll")

        if not poll_channel or not poll_role:
            await inter.response.send_message(
                "Role or channel not found. Please contact an admin.",
                ephemeral=True,
            )
            return

        await poll_channel.send(f"{poll_role.mention}")
        await inter.response.send_message("QOTD Poll announced!", ephemeral=True)

    @qotd.subcommand(name="remove", description="Remove QOTD or QOTD-Poll role.")
    async def qotd_remove(
        self,
        inter: Interaction,
        role_name: str = SlashOption(
            choices=["qotd", "qotd-poll"],
            description="Choose the role to remove.",
        ),
    ):
        """
        Remove the 'qotd' or 'qotd-poll' role from the user.
        """
        response = await self.remove_role(inter.user, role_name)
        await inter.response.send_message(response, ephemeral=True)

    @event.subcommand(name="remove", description="Remove Lounge: Events role.")
    async def event_remove(self, inter: Interaction):
        """
        Remove the 'Lounge: Events' role from the user.
        """
        response = await self.remove_role(inter.user, "Lounge: Events")
        await inter.response.send_message(response, ephemeral=True)

    @commands.Cog.listener("on_ready")
    async def _on_ready(self):
        print(f"Cog {self.__class__.__name__} is ready.")

def setup(bot):
    bot.add_cog(Event(bot))