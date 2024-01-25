from bot_base import APBot
from nextcord import (
    Attachment,
    Embed,
    Interaction,
    Message,
    SlashOption,
    TextChannel,
    Thread,
    User,
    slash_command,
)
from nextcord.ext import application_checks, commands


class Modmail(commands.Cog):
    """Modmail (User proxy) between user and staff"""

    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="mm", description="House all the modmail commands")
    async def _mm(self, inter: Interaction):
        ...

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """
        Sends messages sent from the bot's DMs to the modmail channel.
            - Checks if the message is not from the bot and if the message is not from a server.
            - Creates a modmail embed to send in thread.
        """

        if message.guild or message.author == self.bot.user or message.author not in self.bot.guild.members:
            return

        if message.author.id in await self.bot.db.modmail.get_banned_users():
            await message.author.send(
                embed=Embed(
                    title="Mail from not the mods",
                    description="You are banned from using modmail. Please contact an admin directly for further assistance.",
                )
            )
            return

        content = message.content or "No content"

        # add handling to send messages > 2000 chars
        modmail_embed = Embed(
            title="",
            description=f"```\n{content}\n```",
            color=self.bot.colors["blue"],
        ).set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)

        thread_id = await self.bot.db.modmail.get_channel(message.author.id)
        if thread_id:
            thread = await self.bot.getch_channel(thread_id)
            await thread.send(embed=modmail_embed)
        else:
            modmail_channel: TextChannel = await self.bot.getch_channel(self.bot.config.get("modmail_channel"))
            thread: Thread = await modmail_channel.create_thread(name=f"{message.author} ({message.author.id})", embed=modmail_embed)
            await self.bot.db.modmail.set_channel(message.author.id, thread.id)

        for ind, attachment in enumerate(message.attachments):
            await thread.send(
                embed=Embed(title=f"Attachment {ind+1} / {len(message.attachments)}", color=self.bot.colors["blue"])
                .set_author(name=message.author.name, icon_url=message.author.avatar.url)
                .set_image(url=attachment.url)
            )

        await message.add_reaction("✅")

    @_mm.subcommand(name="send", description="Send a message to the user through modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def send(
        self,
        inter: Interaction,
        message: str = SlashOption(name="message", description="Message to send to the user", required=False),
        attachment: Attachment = SlashOption(name="attachment", description="Attachment to send along with the message", required=False),
    ):
        """
        Send messages to server members (cannot send message to users not in a server with the bot).
            - Generates a response/member embed.
            - Checks if member is in the cooldown list and removes them if so.
        """

        if inter.channel.parent_id != self.bot.config.get("modmail_channel"):
            return await inter.send("You can use that only in modmail threads.", ephemeral=True)

        if not message and not attachment:
            return await inter.send("You must specify a message or an attachment!", ephemeral=True)

        user = await self.bot.getch_user(int(inter.channel.name.split(" ")[-1]))
        send_embed = Embed(title="Mail from the mods.", description=message, color=self.bot.colors["orange"])

        if attachment:
            send_embed.set_image(url=attachment.proxy_url)

        await user.send(embed=send_embed)

        response_embed = Embed(title=f"Message sent to {user.name}", description=f"```\n{message}\n```", color=self.bot.colors["orange"])

        if attachment:
            response_embed.set_image(url=attachment.proxy_url)

        await inter.response.send_message(embed=response_embed)

    @_mm.subcommand(name="ban", description="Ban a user from using modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_ban(
        self,
        inter: Interaction,
        user: User = SlashOption(name="user", description="User to ban. Defaults to current channel author.", required=False),
    ):
        """Bans a user from using modmail"""
        if not user and inter.channel.parent_id != self.bot.config.get("modmail_channel"):
            return await inter.send("You must either specify a user or be present in a modmail thread!", ephemeral=True)

        user_id = user.id if user else int(inter.channel.name.split(" ")[-1])

        await self.bot.db.modmail.ban_user(user_id)
        await inter.send(f"Banned {user.mention} ({user.id}) from modmail", ephemeral=True)

    @_mm.subcommand(name="unban", description="Unan a user from using modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_unban(
        self,
        inter: Interaction,
        user: User = SlashOption(name="user", description="User to unban. Defaults to current channel author.", required=False),
    ):
        """Unbans a user from using modmail"""
        if not user and inter.channel.parent_id != self.bot.config.get("modmail_channel"):
            return await inter.send("You must either specify a user or be present in a modmail thread!", ephemeral=True)

        user_id = user.id if user else int(inter.channel.name.split(" ")[-1])
        await self.bot.db.modmail.unban_user(user_id)
        await inter.send(f"Unbanned user {user} from modmail", ephemeral=True)

    @_mm.subcommand(name="unset_channel", description="Delete the recorded modmail channel for a particular user. User for debugging.")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_unset_channel(self, inter: Interaction, user: User):
        await self.bot.db.modmail.unset_channel(user.id)
        await inter.send("Done", ephemeral=True)


def setup(bot: APBot):
    bot.add_cog(Modmail(bot))
