import asyncio
from datetime import datetime as dt
from typing import List
from uuid import uuid4

from nextcord import (
    Attachment,
    Embed,
    Interaction,
    SlashOption,
    TextChannel,
    ForumChannel,
    Thread,
    User,
    Message,
    slash_command,
)
from nextcord.ext import commands, application_checks

from bot_base import APBot


class Modmail(commands.Cog):
    """Modmail (User proxy) between user and staff"""

    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    async def notify_user(self, user_id: int, message: str, attachment_url: str = None) -> None:
        """Sends a notification to a user."""
        user = await self.bot.getch_user(user_id)
        if not user:
            return

        embed = Embed(title="Mail from the Mods", description=message, color=self.bot.colors["orange"])
        if attachment_url:
            embed.set_image(url=attachment_url)

        await user.send(embed=embed)

    @slash_command(name="mm", description="House all the modmail commands")
    async def _mm(self, inter: Interaction):
        """Base modmail command"""
        ...

    @_mm.subcommand(name="send", description="Send a message to the user through modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_send(
        self,
        inter: Interaction,
        message: str = SlashOption(description="Message to send to the user", required=False),
        attachment: Attachment = SlashOption(description="Attachment to include", required=False),
    ) -> None:
        """Sends a message to a user through modmail."""
        if not inter.channel.parent_id or inter.channel.parent_id != self.bot.config.get("modmail_channel"):
            return await inter.send("This command can only be used in modmail threads.", ephemeral=True)

        user_id = int(inter.channel.name.split("(")[-1].rstrip(")"))
        if not message and not attachment:
            return await inter.send("You must provide a message or an attachment.", ephemeral=True)

        attachment_url = attachment.proxy_url if attachment else None
        await self.notify_user(user_id, message, attachment_url)

        response_embed = Embed(
            title=f"Message sent to {user_id}",
            description=f"```\n{message or 'No content'}\n```",
            color=self.bot.colors["orange"],
        )
        if attachment_url:
            response_embed.set_image(url=attachment_url)

        await inter.response.send_message(embed=response_embed)

    @_mm.subcommand(name="ban", description="Ban a user from using modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_ban(
        self,
        inter: Interaction,
        user: User = SlashOption(description="User to ban"),
    ) -> None:
        """Bans a user from using modmail."""
        await self.bot.db.modmail.ban_user(user.id)
        await inter.response.send_message(f"User {user.mention} has been banned from modmail.", ephemeral=True)

    @_mm.subcommand(name="unban", description="Unban a user from using modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_unban(
        self,
        inter: Interaction,
        user: User = SlashOption(name="user", description="User to unban", required=True),
    ) -> None:
        """Unbans a user from using modmail."""
        await self.bot.db.modmail.unban_user(user.id)
        await inter.response.send_message(f"User {user.mention} has been unbanned from modmail.", ephemeral=True)

    @_mm.subcommand(name="unset_channel", description="Unset the modmail channel for a user (for debugging)")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_unset_channel(
        self,
        inter: Interaction,
        user: User = SlashOption(name="user", description="User whose channel to unset", required=True),
    ) -> None:
        """Removes the modmail channel record for a user."""
        await self.bot.db.modmail.unset_channel(user.id)
        await inter.response.send_message(f"Unset modmail channel for {user.mention}.", ephemeral=True)

@commands.Cog.listener()
async def on_message(self, message: Message):
    """Processes incoming modmail messages."""
    if message.guild or message.author == self.bot.user:
        return

    print(f"Received message from {message.author.id}: {message.content}")  # Debug log

    try:
        # Check if user is banned from modmail
        banned_users = await self.bot.db.modmail.get_banned_users()
        if message.author.id in banned_users:
            await message.author.send(
                embed=Embed(
                    title="Modmail Restricted",
                    description="You are banned from using modmail. Contact an admin for further help.",
                    color=self.bot.colors["red"],
                )
            )
            return

        # Ensure the channel ID is correct
        modmail_channel: ForumChannel = await self.bot.getch_channel(self.bot.config.get("modmail_channel"))
        print(f"Modmail Channel: {modmail_channel}")  # Debug log

        # Get or create thread for the user
        thread_id = await self.bot.db.modmail.get_channel(message.author.id)
        if not thread_id:
            print(f"Creating new thread for {message.author.id}")  # Debug log
            thread = await modmail_channel.create_thread(
                name=f"{message.author} ({message.author.id})",
                content=f"New modmail message from {message.author.mention}",
                auto_archive_duration=1440,  # Set archive time for thread (24 hours)
                applied_tags=[],  # Add forum-specific tags if needed
            )
            await self.bot.db.modmail.set_channel(message.author.id, thread.id)
        else:
            thread = await self.bot.getch_channel(thread_id)

        modmail_embed = Embed(
            title="New Message",
            description=message.content or "No content",
            color=self.bot.colors["blue"],
        ).set_author(name=message.author.name, icon_url=message.author.avatar.url)

        await thread.send(embed=modmail_embed)
        for attachment in message.attachments:
            await thread.send(embed=Embed(title="Attachment", color=self.bot.colors["blue"]).set_image(url=attachment.url))

        # Send a confirmation message to the user that their message has been sent
        await message.author.send(
            embed=Embed(
                title="Your message has been sent",
                description="Your message has been sent to the mod inbox. We will contact you if needed.",
                color=self.bot.colors["green"],
            )
        )

        await message.add_reaction("✅")

    except Exception as e:
        print(f"Error processing modmail message: {e}")
        await message.author.send(
            embed=Embed(
                title="Error",
                description="There was an issue processing your modmail message. Please try again later.",
                color=self.bot.colors["red"],
            )
        )


def setup(bot: APBot):
    bot.add_cog(Modmail(bot))
