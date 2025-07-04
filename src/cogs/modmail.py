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
    ButtonStyle,
)
from nextcord.ext import commands, application_checks
from nextcord.ui import View, button

from bot_base import APBot


class ConfirmView(View):
    def __init__(self, author, on_confirm):
        super().__init__(timeout=60)
        self.author = author
        self.on_confirm = on_confirm

    @button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, button, interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This confirmation prompt isn't for you.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Message sent to mods.", ephemeral=True)
        await self.on_confirm()
        self.stop()

    @button(label="Cancel", style=ButtonStyle.red)
    async def cancel(self, button, interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("This cancel prompt isn't for you.", ephemeral=True)
            return
        await interaction.response.send_message("❌ Cancelled sending message.", ephemeral=True)
        self.stop()


class Modmail(commands.Cog):
    """Modmail (User proxy) between user and staff"""

    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    async def notify_user(self, user_id: int, message: str, attachment_url: str = None) -> None:
        user = await self.bot.getch_user(user_id)
        if not user:
            return
        embed = Embed(title="Message from the mods!", description=message, color=self.bot.colors["orange"])
        if attachment_url:
            embed.set_image(url=attachment_url)
        await user.send(embed=embed)

    @slash_command(name="mm", description="House all the modmail commands")
    async def _mm(self, inter: Interaction):
        ...

    @_mm.subcommand(name="send", description="Send a message to the user through modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_send(
        self,
        inter: Interaction,
        message: str = SlashOption(description="Message to send to the user", required=False),
        attachment: Attachment = SlashOption(description="Attachment to include", required=False),
        user: User = SlashOption(description="User to send to (required outside thread)", required=False),
    ) -> None:
        if not message and not attachment:
            return await inter.send("You must provide a message or attachment.", ephemeral=True)

        if isinstance(inter.channel, Thread) and inter.channel.parent_id == self.bot.config.get("modmail_channel"):
            user_id = await self.bot.db.modmail.get_user(inter.channel.id)
            if not user_id:
                # Try to get user ID from thread name as fallback
                try:
                    user_id = int(inter.channel.name.split('[')[-1].rstrip(']'))
                    await self.bot.db.modmail.set_user(inter.channel.id, user_id)  # Store for future
                except (ValueError, IndexError, AttributeError):
                    return await inter.send("Could not find the user associated with this thread.", ephemeral=True)
        elif user:
            user_id = user.id
        else:
            return await inter.send("You must specify a user if not in a modmail thread.", ephemeral=True)

        attachment_url = attachment.proxy_url if attachment else None
        await self.notify_user(user_id, message, attachment_url)

        recipient = await self.bot.getch_user(user_id)

        response_embed = Embed(
            title=f"Message sent to {recipient}",
            description=f"```\n{message or 'No content'}\n```",
            color=self.bot.colors["orange"]
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
        banned = await self.bot.db.modmail.ban_user(user.id)
        if banned:
            await inter.response.send_message(f"{user.mention} has been banned from modmail.", ephemeral=True)
        else:
            await inter.response.send_message(f"{user.mention} is already banned from modmail.", ephemeral=True)

    @_mm.subcommand(name="unban", description="Unban a user from using modmail")
    @application_checks.has_permissions(moderate_members=True)
    async def _mm_unban(
        self,
        inter: Interaction,
        user: User = SlashOption(name="user", description="User to unban", required=True),
    ) -> None:
        unbanned = await self.bot.db.modmail.unban_user(user.id)
        if unbanned:
            await inter.response.send_message(f"{user.mention} has been unbanned from modmail.", ephemeral=True)
        else:
            await inter.response.send_message(f"{user.mention} was not banned from modmail.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.guild or message.author == self.bot.user:
            return

        try:
            banned_users = await self.bot.db.modmail.get_banned_users()
            if message.author.id in banned_users:
                await message.author.send(
                    embed=Embed(
                        title="Modmail Restricted",
                        description="You are banned from using modmail.",
                        color=self.bot.colors["red"],
                    )
                )
                return

            async def forward_message():
                modmail_channel: ForumChannel = await self.bot.getch_channel(self.bot.config.get("modmail_channel"))
                thread_id = await self.bot.db.modmail.get_channel(message.author.id)

                if not thread_id:
                    thread = await modmail_channel.create_thread(
                        name=f"MODMAIL ------------------------------ {message.author.name} [{message.author.id}]",
                        content="New modmail started.",
                        auto_archive_duration=1440,
                        applied_tags=[],
                    )
                    await self.bot.db.modmail.set_channel(message.author.id, thread.id)
                    await self.bot.db.modmail.set_user(thread.id, message.author.id)
                else:
                    thread = await self.bot.getch_channel(thread_id)

                    expected_name = f"MODMAIL ------------------------------ {message.author.name} [{message.author.id}]"

                    if not isinstance(thread, Thread):
                        # Thread got deleted or is invalid — recreate
                        thread = await modmail_channel.create_thread(
                            name=expected_name,
                            content="Recreated deleted modmail thread.",
                            auto_archive_duration=1440,
                            applied_tags=[],
                        )
                        await self.bot.db.modmail.set_channel(message.author.id, thread.id)
                        await self.bot.db.modmail.set_user(thread.id, message.author.id)
                    else:
                        # ✅ Rename the thread if the name doesn't match expected
                        if thread.name != expected_name:
                            try:
                                await thread.edit(name=expected_name)
                            except Exception as e:
                                print(f"Could not rename thread: {e}")


                # ✅ Format content nicely
                message_text = message.content or "*No content*"
                visual_mention = f"• {message.author.mention}"

                embed = Embed(
                    title="📬 New Message",
                    description=f"{message_text}\n\n{visual_mention}",
                    color=self.bot.colors["orange"],
                    timestamp=message.created_at,
                )
                embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                embed.set_footer(text=f"User ID: {message.author.id}")

                # ✅ Prepare attachments
                files = [await attachment.to_file() for attachment in message.attachments]

                # ✅ Send the final message to the thread
                await thread.send(embed=embed, files=files)




            confirm_embed = Embed(
                title="Confirm Message to Mods",
                description=message.content or "*No content*",
                color=self.bot.colors["orange"],
            ).set_footer(text="Do you want to send this message to the mods?")
            view = ConfirmView(author=message.author, on_confirm=forward_message)
            await message.author.send(embed=confirm_embed, view=view)

        except Exception as e:
            print(f"Error processing modmail: {e}")
            await message.author.send(
                embed=Embed(
                    title="Error",
                    description="Something went wrong. Please try again later.",
                    color=self.bot.colors["red"],
                )
            )


def setup(bot: APBot):
    bot.add_cog(Modmail(bot))
