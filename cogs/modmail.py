from nextcord import Message, TextChannel, Thread, Embed, slash_command, SlashOption, Interaction, Attachment, User, MessageReference
from nextcord.ext import commands, application_checks

from bot_base import APBot


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
        Sends messages sent to the bot's DMs to the modmail channel.
            - Checks if the message is not from the bot and if the message is not from a server.
            - Creates a modmail embed to send in thread.
        """

        if message.guild or message.author == self.bot.user or message.author not in self.bot.guild.members:
            return

        if message.author.id in await self.bot.db.get_modmail_banned_users():
            return

        await message.add_reaction("✅")

        content = message.content or "No content"

        # add handling to send messages > 2000 chars

        modmail_embed = Embed(
            title="",
            description=f"```\n{content}\n```",
            color=self.bot.colors["blue"],
        ).set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )

        thread_id = await self.bot.db.get_user_modmail_channel(message.author.id)
        success = False
        if thread_id:
            try:
                thread = await self.bot.fetch_channel(thread_id)
                await thread.send(embed=modmail_embed)
                success = True
            except:
                pass

        if not success:
            modmail: TextChannel = await self.bot.fetch_channel(self.bot.config.get("modmail_channel"))
            thread: Thread = await modmail.create_thread(
                name=f"{message.author}: {message.author.id}", embed=modmail_embed
            )
            await self.bot.db.set_user_modmail_channel(message.author.id, thread.id)

        for ind, attachment in enumerate(message.attachments):
            await thread.send(
                embed=Embed(
                    title=f"Attachment {ind+1} / {len(message.attachments)}",
                    color=self.bot.colors["blue"]
                ).set_author(
                    name=message.author.name,
                    icon_url=message.author.avatar.url
                ).set_image(
                    url=attachment.url
                )
            )

    @_mm.subcommand(name="send", description="Send a message to the user through modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def send(
        self,
        inter: Interaction,
        message: str = SlashOption(
            name="message",
            description="Message to send to the user",
            required=False
        ),
        attachment: Attachment = SlashOption(
            name="attachment",
            description="Attachment to send along with the message",
            required=False
        )
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

        user = await self.bot.fetch_user(int(inter.channel.name.split(" ")[-1]))
        send_embed = Embed(
            title="Message from the mods.",
            description=message,
            color=self.bot.colors["orange"]
        )
        if attachment:
            send_embed.set_image(url=attachment.proxy_url)

        await user.send(embed=send_embed)

        response_embed = Embed(
            title=f"Message sent to {user.name}",
            description=f"```\n{message}\n```",
            color=self.bot.colors["orange"]
        )

        if attachment:
            response_embed.set_image(url=attachment.proxy_url)

        await inter.response.send_message(embed=response_embed)

    @_mm.subcommand(name="archive", description="Archive a modmoail thread")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_archive(self, inter: Interaction):
        if inter.channel.parent_id != self.bot.config.get("modmail_channel"):
            return await inter.send("You can use that only in modmail threads.", ephemeral=True)

        await inter.channel.edit(archived=True)
        await inter.send("Archived this thread.", ephemeral=True)

    @_mm.subcommand(name="ban", description="Ban a user from using modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_ban(self, inter: Interaction, user: User = SlashOption(name="user", description="User to ban", required=False)):
        if not user and inter.channel.parent_id != self.bot.config.get("modmail_channel"):
            return await inter.send("You must either specify a user or be present in a modmail thread!", ephemeral=True)

        user_id = user.id if user else int(inter.channel.name.split(" ")[-1])
        await self.bot.db.ban_modmail_user(user_id)
        await inter.send(f"Banned user {user} from modmail", ephemeral=True)

    @_mm.subcommand(name="unban", description="Unan a user from using modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_unban(self, inter: Interaction, user: User = SlashOption(name="user", description="User to unban", required=False)):
        if not user and inter.channel.parent_id != self.bot.config.get("modmail_channel"):
            return await inter.send("You must either specify a user or be present in a modmail thread!", ephemeral=True)

        user_id = user.id if user else int(inter.channel.name.split(" ")[-1])
        await self.bot.db.unban_modmail_user(user_id)
        await inter.send(f"Unbanned user {user} from modmail", ephemeral=True)

def setup(bot: APBot):
    bot.add_cog(Modmail(bot))
