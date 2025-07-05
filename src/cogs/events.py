from nextcord import (
    Interaction,
    SlashOption,
    ButtonStyle,
    ui,
    slash_command,
    Embed
)
from nextcord.ext import commands
from nextcord.utils import get


class RoleSubscribeView(ui.View):
    def __init__(self, role_name: str, label_suffix: str):
        super().__init__(timeout=None)
        self.role_name = role_name
        self.label_suffix = label_suffix

    @ui.button(label="Click here to be notified!", style=ButtonStyle.secondary)
    async def toggle(self, button: ui.Button, inter: Interaction):
        role = get(inter.guild.roles, name=self.role_name)
        if not role:
            return await inter.response.send_message(
                f"Role `{self.role_name}` no longer exists.", ephemeral=True
            )

        if role in inter.user.roles:
            await inter.user.remove_roles(role)
            await inter.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await inter.user.add_roles(role)
            await inter.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class ConfirmPingView(ui.View):
    def __init__(self, caller_inter: Interaction, role_name: str, channel_name: str, label_suffix: str):
        super().__init__(timeout=60)
        self.caller_inter = caller_inter
        self.role_name = role_name
        self.channel_name = channel_name
        self.label_suffix = label_suffix

    @ui.button(label="Confirm", style=ButtonStyle.success)
    async def confirm(self, button: ui.Button, inter: Interaction):
        if inter.user.id != self.caller_inter.user.id:
            return await inter.response.send_message(
                "Only the command author can confirm this.", ephemeral=True
            )

        role = get(inter.guild.roles, name=self.role_name)
        channel = get(inter.guild.channels, name=self.channel_name)

        if not role or not channel:
            await inter.response.edit_message(
                content="Role or channel vanished; aborting.",
                view=None
            )
            return await inter.message.delete()

        sub_view = RoleSubscribeView(self.role_name, self.label_suffix)
        sub_view.children[0].label = f"Click here to be notified for future {self.label_suffix}!"
        sub_view.children[0].style = ButtonStyle.secondary

        await channel.send(content=role.mention, view=sub_view)

        await inter.response.edit_message(
            content="✅ Ping sent successfully!",
            view=None
        )
        await inter.message.delete()

    @ui.button(label="Cancel", style=ButtonStyle.danger)
    async def cancel(self, button: ui.Button, inter: Interaction):
        if inter.user.id != self.caller_inter.user.id:
            return await inter.response.send_message(
                "Only the command author can cancel this.", ephemeral=True
            )

        await inter.response.edit_message(
            content="❌ Ping cancelled.",
            view=None
        )
        await inter.message.delete()


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def toggle_role(self, member, role_name: str) -> str:
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
        pass

    @event.subcommand(name="notify", description="Toggle notifications for events.")
    async def event_notify(self, inter: Interaction):
        response = await self.toggle_role(inter.user, "Lounge: Events")
        await inter.response.send_message(response, ephemeral=True)

    @event.subcommand(name="announce", description="Announce an event.")
    async def event_announce(self, inter: Interaction):
        if not any(role.name in ["Event Coordinator", "Chat Moderator"] for role in inter.user.roles):
            return await inter.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )

        role = get(inter.guild.roles, name="Lounge: Events")
        channel = get(inter.guild.channels, name="events")

        if not role or not channel:
            return await inter.response.send_message(
                "Role or channel not found. Please contact an admin.", ephemeral=True
            )

        view = ConfirmPingView(inter, "Lounge: Events", "events", "events")

        await inter.response.send_message(
            "Please confirm that you would like to ping the events role in the events channel.",
            view=view,
            ephemeral=False,
        )

    @event.subcommand(name="remove", description="Remove Lounge: Events role.")
    async def event_remove(self, inter: Interaction):
        response = await self.remove_role(inter.user, "Lounge: Events")
        await inter.response.send_message(response, ephemeral=True)

    @slash_command(name="qotd", description="Manage QOTD roles and announcements.")
    async def qotd(self, inter: Interaction):
        pass

    @qotd.subcommand(name="role", description="Toggle QOTD or QOTD-Poll role.")
    async def qotd_role(
        self,
        inter: Interaction,
        role_name: str = SlashOption(
            choices=["qotd", "qotd-poll"],
            description="Choose the role to toggle.",
        ),
    ):
        response = await self.toggle_role(inter.user, role_name)
        await inter.response.send_message(response, ephemeral=True)

    @qotd.subcommand(name="announce", description="Ping the QOTD role.")
    async def qotd_announce(self, inter: Interaction):
        if not any(role.name in ["QOTD Curator", "Chat Moderator"] for role in inter.user.roles):
            return await inter.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )

        if inter.channel and inter.channel.name != "qotd":
            return await inter.response.send_message(
                "This command can only be run in the 'qotd' channel.", ephemeral=True
            )

        view = ConfirmPingView(inter, "qotd", "qotd", "qotd")

        await inter.response.send_message(
            "Please confirm that you would like to ping the QOTD role in the qotd channel.",
            view=view,
            ephemeral=False,
        )

    @qotd.subcommand(name="poll", description="Ping the QOTD-Poll role.")
    async def qotd_poll(self, inter: Interaction):
        if not any(role.name in ["QOTD Curator", "Chat Moderator"] for role in inter.user.roles):
            return await inter.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )

        if inter.channel and inter.channel.name != "qotd-poll":
            return await inter.response.send_message(
                "This command can only be run in the 'qotd-poll' channel.", ephemeral=True
            )

        view = ConfirmPingView(inter, "qotd-poll", "qotd-poll", "qotd-poll")

        await inter.response.send_message(
            "Please confirm that you would like to ping the QOTD-Poll role in the qotd-poll channel.",
            view=view,
            ephemeral=False,
        )

    @qotd.subcommand(name="remove", description="Remove QOTD or QOTD-Poll role.")
    async def qotd_remove(
        self,
        inter: Interaction,
        role_name: str = SlashOption(
            choices=["qotd", "qotd-poll"], description="Choose the role to remove."
        ),
    ):
        response = await self.remove_role(inter.user, role_name)
        await inter.response.send_message(response, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(RoleSubscribeView("Lounge: Events", "events"))
        self.bot.add_view(RoleSubscribeView("qotd", "qotd"))
        self.bot.add_view(RoleSubscribeView("qotd-poll", "qotd-poll"))
        print(f"Cog {self.__class__.__name__} is ready.")


def setup(bot):
    bot.add_cog(Events(bot))
