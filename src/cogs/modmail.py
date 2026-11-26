import asyncio
import re
from collections import deque
from datetime import datetime as dt
from typing import List, Optional
import time  # <-- added for deduplication

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
from nextcord.ext import commands
from nextcord.ui import View, button
from nextcord.ui import Button, Modal, TextInput
from nextcord import TextInputStyle
from bot_base import APBot
from config_handler import Config
import nextcord

config_path = "config.json"
conf = Config(config_path)

REQUIRED_ROLES = {"Trial Chat Moderator", "Chat Moderator", "Admin"}
MAIN_MOD =  {"Moderator"}



# ============================================================
#                CONFIRM VIEW (USED BY BOTH)
# ============================================================

class ConfirmView(View):
    def __init__(self, author: User, on_confirm, on_cancel=None, post_confirm_note=None, verify_delivery=False):
        super().__init__(timeout=60)
        self.author = author
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.message = None
        self.post_confirm_note = post_confirm_note  # Optional text to send AFTER confirmation
        self.verify_delivery = verify_delivery

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "This confirmation prompt isn't for you.", ephemeral=True
            )
            return False
        return True

    @button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, button, interaction: Interaction):
        embed = interaction.message.embeds[0]
        if self.verify_delivery:
            # Acknowledge first, then report success only after forwarding.
            embed.title = "Sending..."
            embed.set_footer(text="Forwarding your message to the mods.")
            await interaction.response.edit_message(embed=embed, view=None)
            try:
                await self.on_confirm()
            except Exception as error:
                print(f"[Modmail] Message forwarding failed: {error}")
                embed.color = 0xED4245
                embed.title = "Message not sent"
                embed.set_footer(text="Please try again or contact a moderator.")
            else:
                embed.color = 0x57F287
                embed.title = "Confirmed"
                embed.set_footer(text="Message sent successfully.")
            self.stop()
            await interaction.message.edit(embed=embed, view=None)
            if embed.title == "Confirmed" and self.post_confirm_note:
                await interaction.followup.send(self.post_confirm_note, ephemeral=True)
            return
        embed.color = 0x57F287
        embed.title = "Confirmed"
        embed.set_footer(text="Message sent successfully.")
        await interaction.response.edit_message(embed=embed, view=None)
        await self.on_confirm()

        # Send post-confirmation note if specified
        if self.post_confirm_note:
            await interaction.followup.send(self.post_confirm_note, ephemeral=True)

        self.stop()

    @button(label="Cancel", style=ButtonStyle.red)
    async def cancel(self, button, interaction: Interaction):
        embed = interaction.message.embeds[0]
        embed.color = 0xED4245
        embed.title = "Request Cancelled"
        embed.set_footer(text="Message was not sent.")
        await interaction.response.edit_message(embed=embed, view=None)
        if self.on_cancel:
            await self.on_cancel()
        self.stop()

    async def on_timeout(self):
        if self.message:
            embed = self.message.embeds[0]
            embed.color = 0x808080
            embed.title = "Timeout"
            embed.set_footer(text="Time to confirm/deny has been exhausted.")
            await self.message.edit(embed=embed, view=None)


# ============================================================
#                      MODMAIL COG
# ============================================================

class Modmail(commands.Cog):
    """Modmail (User proxy) between user and staff"""

    def __init__(self, bot: APBot) -> None:
        self.bot = bot
        self._recent_messages: deque[tuple[tuple[int, int], float]] = deque(maxlen=100)

    def _has_required_role(self, inter: Interaction) -> bool:
        return any(role.name in REQUIRED_ROLES for role in inter.user.roles)

    async def _get_modmail_access_denial(
        self,
        user: User,
    ) -> Optional[Embed]:
        """Return an error embed when a user cannot access modmail.

        Check order:
        1. Server ban
        2. Modmail ban
        3. Current AP Students membership
        """

        guild = self.bot.get_guild(self.bot.config.get("guild_id"))
        if guild is None:
            return Embed(
                title="Modmail Unavailable",
                description="Modmail is temporarily unavailable. Please try again later.",
                color=self.bot.colors["red"],
            )

        # Check the server ban first. Banned users are no longer guild members,
        # so this must happen before the membership check.
        try:
            await guild.fetch_ban(user)
            return Embed(
                title="Modmail Restricted",
                description="You are banned from AP Students and cannot use modmail.",
                color=self.bot.colors["red"],
            )
        except nextcord.NotFound:
            pass
        except (nextcord.Forbidden, nextcord.HTTPException) as error:
            print(
                f"Could not check server ban status for {user.id}: {error}"
            )
            return Embed(
                title="Modmail Unavailable",
                description="Modmail is temporarily unavailable. Please try again later.",
                color=self.bot.colors["red"],
            )

        # Keep the existing separate modmail-ban system.
        try:
            banned_users = await self.bot.db.modmail.get_banned_users()
        except Exception as error:
            print(
                f"Could not check modmail ban status for {user.id}: {error}"
            )
            return Embed(
                title="Modmail Unavailable",
                description="Modmail is temporarily unavailable. Please try again later.",
                color=self.bot.colors["red"],
            )

        if user.id in banned_users:
            return Embed(
                title="Modmail Restricted",
                description="You are banned from using modmail.",
                color=self.bot.colors["red"],
            )

        # Use the cache first, then fetch directly so this works reliably in a
        # large server where every member may not be cached.
        member = guild.get_member(user.id)
        if member is None:
            try:
                await guild.fetch_member(user.id)
            except nextcord.NotFound:
                return Embed(
                    title="Server Membership Required",
                    description=(
                        "You must be a member of AP Students to use modmail. "
                        "Join the server, then try again."
                    ),
                    color=self.bot.colors["orange"],
                )
            except (nextcord.Forbidden, nextcord.HTTPException) as error:
                print(
                    f"Could not check server membership for {user.id}: {error}"
                )
                return Embed(
                    title="Modmail Unavailable",
                    description=(
                        "Modmail is temporarily unavailable. Please try again later."
                    ),
                    color=self.bot.colors["red"],
                )

        return None

    @staticmethod
    def _modmail_title_user_id(name: str) -> Optional[int]:
        # v3.1: MODMAIL ---- username [id]; v3.0: username#0: id
        match = re.fullmatch(r"MODMAIL\s+-+\s+.+\s+\[(\d{17,20})\]", name)
        if match is None:
            match = re.fullmatch(r".+?:\s*(\d{17,20})", name)
        return int(match.group(1)) if match else None

    def _modmail_thread_name(self, user: User) -> str:
        return f"MODMAIL ------------------------------ {user.name} [{user.id}]"

    def _modmail_lock(self):
        # Shared by the listener, staff replies and thread reopen events.
        lock = getattr(self.bot, "_modmail_thread_lock", None)
        if lock is None:
            lock = self.bot._modmail_thread_lock = asyncio.Lock()
        return lock

    def _is_modmail_thread(self, thread) -> bool:
        return (
            isinstance(thread, Thread)
            and thread.parent_id == int(self.bot.config.get("modmail_channel"))
        )

    async def _fetch_modmail_thread(self, thread_id: int):
        # Archived posts may not be cached. Only an actual Unknown Channel
        # response means the post is gone; permission/API failures must surface.
        try:
            thread = await self.bot.fetch_channel(int(thread_id))
        except nextcord.NotFound as error:
            if error.code == 10003:
                return None
            raise
        if not self._is_modmail_thread(thread):
            raise RuntimeError("Stored modmail ID is not a thread in the modmail forum.")
        return thread

    async def _repair_modmail_thread(self, thread, user_id: int, user=None, reopen=False):
        if not self._is_modmail_thread(thread):
            raise RuntimeError("Not a modmail forum thread.")
        db = self.bot.db.modmail
        reverse = await db.get_user(thread.id)
        owners = await db.user_config.find(
            {"modmail_id": thread.id}, {"user_id": 1}
        ).to_list(length=None)
        if any(d.get("user_id") != user_id for d in owners):
            raise RuntimeError("Another user is mapped to this modmail thread.")
        title_id = self._modmail_title_user_id(thread.name)
        if reverse is not None and int(reverse) != user_id:
            raise RuntimeError("Modmail thread is mapped to a different user.")
        if title_id is not None and title_id != user_id:
            raise RuntimeError("Modmail title identifies a different user.")
        forward = await db.get_channel(user_id)
        if forward is not None and int(forward) != thread.id:
            other = await self._fetch_modmail_thread(forward)
            if other is not None:
                raise RuntimeError("User has another existing modmail thread; staff review required.")
        if reopen and thread.archived:
            if thread.locked:
                raise RuntimeError("Modmail thread is locked; staff must reopen it.")
            thread = await thread.edit(archived=False)
        if reverse is None:
            await db.set_user(thread.id, user_id)
        if forward is None or int(forward) != thread.id:
            await db.set_channel(user_id, thread.id)
        if user is not None and not thread.archived:
            expected = self._modmail_thread_name(user)
            if thread.name != expected:
                try:
                    thread = await thread.edit(name=expected)
                except nextcord.HTTPException as error:
                    # A title edit failure should not prevent a verified reply.
                    print(f"[Modmail] Could not rename thread {thread.id}: {error}")
        return thread

    async def _resolve_modmail_thread_user(self, thread, explicit_user=None, reopen=True):
        # Called with the lock held. Never route a DM if identity is ambiguous.
        thread = await self._fetch_modmail_thread(thread.id)
        if thread is None:
            raise RuntimeError("Modmail thread no longer exists.")
        reverse = await self.bot.db.modmail.get_user(thread.id)
        title_id = self._modmail_title_user_id(thread.name)
        owners = await self.bot.db.modmail.user_config.find(
            {"modmail_id": thread.id}, {"user_id": 1}
        ).to_list(length=None)
        owner_ids = {d.get("user_id") for d in owners}
        identities = owner_ids | {int(reverse) if reverse is not None else None, title_id}
        identities.discard(None)
        if len(identities) > 1:
            raise RuntimeError("Conflicting modmail user identities; staff review required.")
        user_id = next(iter(identities), None)
        if user_id is None:
            raise RuntimeError("Cannot identify the user from the database or thread title.")
        if explicit_user is not None and explicit_user.id != user_id:
            raise RuntimeError("Selected user does not match this modmail thread.")
        user = explicit_user or await self.bot.fetch_user(user_id)
        await self._repair_modmail_thread(thread, user_id, user=user, reopen=reopen)
        return user

    async def _get_user_modmail_thread(self, user: User, create=False):
        async with self._modmail_lock():
            db = self.bot.db.modmail
            thread_id = await db.get_channel(user.id)
            thread = await self._fetch_modmail_thread(thread_id) if thread_id else None
            if thread is None:
                # Recover the reverse mapping if the forward mapping was lost.
                candidates = await db.channel_config.find(
                    {"modmail_user_id": user.id}, {"channel_id": 1}
                ).to_list(length=None)
                existing = []
                for candidate_id in {d.get("channel_id") for d in candidates if d.get("channel_id")}:
                    candidate = await self._fetch_modmail_thread(candidate_id)
                    if candidate is not None:
                        existing.append(candidate)
                if len(existing) > 1:
                    raise RuntimeError("Multiple modmail threads found; staff review required.")
                if existing:
                    thread = existing[0]
            if thread is None:
                if not create:
                    return None
                forum = await self.bot.fetch_channel(int(self.bot.config.get("modmail_channel")))
                if not isinstance(forum, ForumChannel):
                    raise RuntimeError("Modmail forum is unavailable.")
                created = await forum.create_thread(
                    name=self._modmail_thread_name(user),
                    content="Recreated deleted modmail thread." if thread_id else "New modmail started.",
                    auto_archive_duration=1440,
                )
                thread = created if isinstance(created, Thread) else created.thread
            return await self._repair_modmail_thread(thread, user.id, user=user, reopen=True)

    @commands.Cog.listener()
    async def on_thread_update(self, before: Thread, after: Thread):
        # Lazy migration: repair legacy names when staff reopen an archived post.
        if not before.archived or after.archived or not self._is_modmail_thread(after):
            return
        try:
            async with self._modmail_lock():
                await self._resolve_modmail_thread_user(after, reopen=False)
        except Exception as error:
            print(f"[Modmail] Could not reconcile reopened thread {after.id}: {error}")


    async def notify_user(self, user_id: int, message: str, attachment_url: str = None) -> None:
        user = await self.bot.getch_user(user_id)
        if not user:
            raise RuntimeError("Modmail recipient could not be fetched.")
        embed = Embed(title="Message from the mods!", description=message, color=self.bot.colors["orange"])
        if attachment_url:
            embed.set_image(url=attachment_url)
        await user.send(embed=embed)

    @slash_command(name="mm", description="House all the modmail commands", guild_ids=[conf.get("guild_id")])
    async def _mm(self, inter: Interaction):
        ...

    @_mm.subcommand(name="send", description="Send a message to the user through modmail")
    async def _mm_send(
        self,
        inter: Interaction,
        message: str = SlashOption(description="Message to send to the user", required=False),
        attachment: Attachment = SlashOption(description="Attachment to include", required=False),
        user: User = SlashOption(description="User to send to (required outside thread)", required=False),
    ) -> None:
        if not self._has_required_role(inter):
            return await inter.send("You don't have permission to use this command.", ephemeral=True)

        if not message and not attachment:
            return await inter.send("You must provide a message or attachment.", ephemeral=True)

        in_thread = self._is_modmail_thread(inter.channel)
        if not in_thread and not user:
            return await inter.send("You must specify a user if not in a modmail thread.", ephemeral=True)

        await inter.response.defer()
        try:
            if in_thread:
                async with self._modmail_lock():
                    recipient = await self._resolve_modmail_thread_user(inter.channel, user)
            else:
                recipient = user
            attachment_url = attachment.proxy_url if attachment else None
            await self.notify_user(recipient.id, message, attachment_url)
        except Exception as error:
            print(f"[Modmail] Staff reply failed: {error}")
            return await inter.followup.send(
                "Could not send modmail. Check the thread/user mapping or bot logs.",
                ephemeral=True,
            )

        response_embed = Embed(
            title=f"Message sent to {recipient}",
            description=f"```\n{message or 'No content'}\n```",
            color=self.bot.colors["orange"]
        )
        if attachment_url:
            response_embed.set_image(url=attachment_url)

        await inter.followup.send(embed=response_embed)

    @_mm.subcommand(name="ban", description="Ban a user from using modmail")
    async def _mm_ban(self, inter: Interaction, user: User):
        if not self._has_required_role(inter):
            return await inter.send("You don't have permission to use this command.", ephemeral=True)

        banned = await self.bot.db.modmail.ban_user(user.id)
        msg = f"{user.mention} has been banned from modmail." if banned else f"{user.mention} is already banned."
        await inter.response.send_message(msg, ephemeral=True)

    @_mm.subcommand(name="unban", description="Unban a user from using modmail")
    async def _mm_unban(self, inter: Interaction, user: User):
        if not self._has_required_role(inter):
            return await inter.send("You don't have permission to use this command.", ephemeral=True)

        unbanned = await self.bot.db.modmail.unban_user(user.id)
        msg = f"{user.mention} has been unbanned from modmail." if unbanned else f"{user.mention} was not banned."
        await inter.response.send_message(msg, ephemeral=True)

    # ============================================================
    #               MAIN LISTENER (with deduplication)
    # ============================================================
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.guild:
            return
        if message.author.id == self.bot.user.id:
            return
        if message.type != nextcord.MessageType.default:
            return
        if message.embeds or message.components:
            return

        now = time.time()
        msg_key = (message.id, message.author.id)
        while self._recent_messages and self._recent_messages[0][1] < now - 5:
            self._recent_messages.popleft()
        if any(key == msg_key for key, _ in self._recent_messages):
            return
        self._recent_messages.append((msg_key, now))

        try:
            denial_embed = await self._get_modmail_access_denial(message.author)
            if denial_embed is not None:
                await message.author.send(embed=denial_embed)
                return

            async def forward_message():
                # Recheck access at confirmation time, not just when the DM arrived.
                denial = await self._get_modmail_access_denial(message.author)
                if denial is not None:
                    await message.author.send(embed=denial)
                    raise RuntimeError("Modmail access denied at confirmation.")
                thread = await self._get_user_modmail_thread(message.author, create=True)

                message_text = message.content or "*No content*"
                visual_mention = f"• {message.author.mention}"

                embed = Embed(
                    title="New Message",
                    description=f"{message_text}\n\n{visual_mention}",
                    color=self.bot.colors["orange"],
                    timestamp=message.created_at,
                )
                embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                embed.set_footer(text=f"User ID: {message.author.id}")

                files = [await attachment.to_file() for attachment in message.attachments]
                await thread.send(embed=embed, files=files)

            confirm_embed = Embed(
                title="Confirm Message to Mods",
                description=message.content or "*No content*",
                color=self.bot.colors["orange"],
            )
            confirm_embed.set_footer(text="Do you want to send this message to the mods? • Modmail Confirmation")

            async def cancel_action():
                pass

            post_confirm_note = "-# If the message requires immediate action, try `/emergency`."

            view = ConfirmView(
                author=message.author,
                on_confirm=forward_message,
                on_cancel=cancel_action,
                post_confirm_note=post_confirm_note,
                verify_delivery=True,
            )

            msg_sent = await message.author.send(embed=confirm_embed, view=view)
            view.message = msg_sent

        except Exception as e:
            print(f"Error processing modmail: {e}")
            try:
                await message.author.send(
                    embed=Embed(
                        title="Error",
                        description="Something went wrong. Please try again later.",
                        color=self.bot.colors["red"],
                    )
                )
            except Exception:
                pass

    # ============================================================
    # 🔥 ADDED: EMERGENCY TRIGGER HANDLER
    # ============================================================
    async def trigger_emergency(self, user: User):
        """Handles notifying all moderators of an emergency alert in the user's modmail thread."""

        denial_embed = await self._get_modmail_access_denial(user)
        if denial_embed is not None:
            await user.send(embed=denial_embed)
            return

        guild = self.bot.get_guild(self.bot.config.get("guild_id"))
        if not guild:
            await user.send("Could not find the guild configuration. Please contact an admin.")
            return

        mod_role = next((r for r in guild.roles if r.name in MAIN_MOD), None)
        if not mod_role:
            await user.send("Could not find a moderator role to ping.")
            return

        try:
            thread = await self._get_user_modmail_thread(user, create=False)
        except Exception as error:
            print(f"[Modmail] Emergency thread lookup failed: {error}")
            await user.send("Could not access your modmail thread. Please contact a moderator.")
            return
        if thread is None:
            await user.send("You don't have an active modmail thread. Please send a message first to start one.")
            return

        # Build emergency embed
        embed = Embed(
            title="EMERGENCY ALERT",
            description=(
                f"{user.mention} has triggered an **emergency alert**!\n\n"
                "Please respond **immediately**."
            ),
            color=0xED4245,
            timestamp=dt.utcnow(),
        )
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)
        embed.set_footer(text=f"User ID: {user.id} • Triggered via /emergency")

        # Send directly into the user's thread
        try:
            await thread.send(content=mod_role.mention, embed=embed)
        except Exception as e:
            await user.send("Failed to send emergency alert. Please try again or contact an admin.")
            print(f"Failed to send emergency in thread {thread.id}: {e}")
            return

    # ============================================================
    # MODAL for Emergency Confirmation
    # ============================================================
    class EmergencyModal(Modal):
        def __init__(self, parent_inter: Interaction, bot):
            super().__init__("Emergency Acknowledgment")
            self.parent_inter = parent_inter
            self.bot = bot

            self.confirm_field = TextInput(
                label="Type the confirmation phrase below:",
                placeholder="I understand and agree to the conditions above.",
                style=TextInputStyle.short,
                required=True,
            )
            self.add_item(self.confirm_field)

        async def callback(self, interaction: Interaction):
            phrase = self.confirm_field.value.strip()
            expected = "I understand and agree to the conditions above."
            if phrase.lower() != expected.lower():
                await interaction.response.send_message(
                    "You must type the phrase exactly as shown to continue.", ephemeral=True
                )
                return

            confirm_embed = Embed(
                title="Confirm Emergency Alert",
                description="Press **Confirm** to alert all moderators.",
                color=0xFEE75C,
            )

            async def trigger():
                db = interaction.client.db

                # 🔒 START cooldown HERE
                await db.emergency.set_cooldown(interaction.user.id, minutes=60 * 24)

                await interaction.client.get_cog("Modmail").trigger_emergency(interaction.user)


            async def cancel_action():
                pass

            view = ConfirmView(author=interaction.user, on_confirm=trigger, on_cancel=cancel_action)

            await interaction.response.defer(ephemeral=True)
            msg = await interaction.followup.send(embed=confirm_embed, view=view)
            view.message = msg

    # ============================================================
    # BUTTON VIEW to trigger modal
    # ============================================================
    class EmergencyView(View):
        def __init__(self, bot, author: User):
            super().__init__(timeout=90)
            self.bot = bot
            self.author = author

        async def interaction_check(self, interaction: Interaction) -> bool:
            if interaction.user != self.author:
                await interaction.response.send_message(
                    "This button isn't for you.", ephemeral=True
                )
                return False
            return True

        @button(label="Acknowledge Terms", style=ButtonStyle.blurple)
        async def acknowledge(self, button: Button, interaction: Interaction):
            button.disabled = True
            modal = Modmail.EmergencyModal(interaction, self.bot)
            await interaction.response.send_modal(modal)
            try:
                await interaction.message.edit(view=None)
            except Exception:
                pass
            self.stop()


        @button(label="Cancel Request", style=ButtonStyle.red)
        async def cancel(self, button: Button, interaction: Interaction):
            embed = interaction.message.embeds[0]
            embed.title = "Request Denied"
            embed.description = "You have canceled the emergency request. No action was taken."
            embed.color = 0xED4245
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()

    # ============================================================
    # UPDATED /EMERGENCY COMMAND
    # ============================================================
    @slash_command(name="emergency", description="Ping moderators in an emergency (DM only)")
    async def _emergency(self, inter: Interaction):
        if inter.guild:
            return await inter.send("This command can only be used in DMs.", ephemeral=True) 
        
        denial_embed = await self._get_modmail_access_denial(inter.user)
        if denial_embed is not None:
            return await inter.send(embed=denial_embed, ephemeral=True)

        allowed, reason = await self.bot.db.emergency.can_use(inter.user.id, self.bot.db)
        if not allowed:
            return await inter.send(reason, ephemeral=True)
        embed = Embed(
            title="Emergency Confirmation Required",
            description=(
                "**What you are about to do will ping all moderators.** Please read carefully.\n\n"
                "You are only allowed to use this command in *true emergency situations*, such as:\n"
                "• Someone spamming NSFW content\n"
                "• A dangerous or suspicious link being posted\n"
                "• A raid in progress\n"
                "• A serious report, such as someone being a potential predator\n\n"
                "You may **NOT** use this command to:\n"
                "• Appeal a mute or ban\n"
                "• Request a helper role\n"
                "• Handle non-urgent issues that don’t require immediate moderator action\n\n"
                "Misusing or abusing this command can result in moderator action and/or a permanent ban from ModMail.\n\n"
                "**To continue, click the button below and type the confirmation phrase.**"
            ),
            color=0xED4245,
        )

        await inter.response.send_message (
        embed=embed,
        view=self.EmergencyView(self.bot, inter.user),
    )



def setup(bot: APBot):
    bot.add_cog(Modmail(bot))