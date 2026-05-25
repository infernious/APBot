import nextcord
from nextcord import (
    slash_command,
    Permissions,
    Interaction,
    Embed,
    Member,
    TextChannel,
    SlashOption,
    Attachment,
    Forbidden,
    Color,
)
from datetime import datetime, timedelta, timezone
from nextcord.ext import commands, tasks
import asyncio
from typing import Union, Optional
from bot_base import APBot
from app_config import get_command_guild_ids, load_optional_config
from cogs.utils import convert_time 

conf = load_optional_config()
COMMAND_GUILD_IDS = get_command_guild_ids(conf)

class Infraction:
    def __init__(
        self,
        actiontype: str,
        reason: str,
        moderator: Member,
        actiontime: datetime,
        duration: Optional[int] = None,  # Duration in seconds, default is None
        attachment_url: Optional[str] = None  # URL of any attachments, default is None
    ):
        self.actiontype = actiontype
        self.reason = reason
        self.moderator = moderator
        self.actiontime = actiontime
        self.duration = duration
        self.attachment_url = attachment_url

class ModerationCommands(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot
    def cog_load(self) -> None:
        if not self.restricted_cleanup_loop.is_running():
            self.restricted_cleanup_loop.start()
    def cog_unload(self) -> None:
        if self.restricted_cleanup_loop.is_running():
            self.restricted_cleanup_loop.cancel()
    def has_mod_role(self, member: Member) -> bool:
        allowed_roles = {"Trial Chat Moderator", "Chat Moderator", "Moderator", "Admin"}
        return any(role.name in allowed_roles for role in member.roles)

    @slash_command(
        name="warnchannel",
        description="Send a warning to a channel and temporarily modify permissions",
        default_member_permissions=Permissions(moderate_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def warnchannel(
        self,
        inter: Interaction,
        reason: str = SlashOption(description="The reason for the warning", required=False),
    ):
        await inter.response.defer(ephemeral=True)

        # Send warning message to the channel
        await inter.channel.send(
            embed=Embed(
                title="Channel Warn",
                description=f"⚠️ {reason}",
                color=self.bot.colors.get("red", Color.red()),
            ).set_footer(text="This channel will be unlocked soon. Go touch grass in the meantime.")
        )

        # Temporarily change permissions
        await inter.channel.set_permissions(inter.guild.default_role, send_messages=False)
        await inter.followup.send("Done", ephemeral=True)

        # Send log message to the logs channel (by name, not ID)
        logs_channel: Optional[TextChannel] = nextcord.utils.get(inter.guild.text_channels, name="logs")

        if isinstance(logs_channel, TextChannel):
            try:
                await logs_channel.send(embed=Embed(
                    title="Channel Warn",
                    description=(
                        f"Responsible Mod: {inter.user.mention}\n"
                        f"Reason: {reason if reason else 'No Reason Given.'}"
                    ),
                    color=self.bot.colors.get("light_orange")
                ).set_footer(text=f"Issued by: {inter.user.display_name} ({inter.user.mention})"))
            except Forbidden:
                await inter.followup.send("Failed to send a message to the logs channel. Check the bot's permissions.", ephemeral=True)
        else:
            await inter.followup.send("Logs channel named `logs` not found in this server.", ephemeral=True)

        # Unlock channel, set slowmode, and revert permissions after 5 minutes
        await asyncio.sleep(60 * 5)  # Wait for 5 minutes
        await inter.channel.edit(slowmode_delay=15)
        await inter.channel.set_permissions(inter.guild.default_role, send_messages=True)


    async def infraction_response(
        self,
        interaction: Interaction,
        member: Union[Member, nextcord.User],
        infraction: Infraction
    ) -> None:
        infraction_details = {
            "warn": ("Warning", self.bot.colors.get("yellow")),
            "mute": ("Mute", self.bot.colors.get("orange")),
            "pseudo-mute": ("Mute", self.bot.colors.get("light_orange")),
            "unmute": ("Unmute", self.bot.colors.get("green")),
            "kick": ("Kick", self.bot.colors.get("dark_orange")),
            "ban": ("Ban", self.bot.colors.get("red")),
            "force-ban": ("Force-Ban", self.bot.colors.get("red")),
            "unban": ("Unban", self.bot.colors.get("green")),
            "note": ("Internal Note", Color.purple()), 
        }

        infraction_name, color = infraction_details.get(
            infraction.actiontype, ("Infraction", nextcord.Color.default())
        )

        # Base embed for both user and logs
        base_embed = Embed(
            title=f"Infraction: {infraction_name}",
            description=f"**Reason:**\n{infraction.reason}",
            color=color,
            timestamp=infraction.actiontime,
        )

        if infraction.duration:
            mute_end = int((infraction.actiontime + timedelta(seconds=infraction.duration)).timestamp())
            base_embed.add_field(
                name="**Unmute:**",
                value=f"<t:{mute_end}:f> (<t:{mute_end}:R>)",
                inline=False,
            )

        if infraction.attachment_url:
            base_embed.set_image(url=infraction.attachment_url)

        # Use display_name if Member, username if User
        try:
            name = member.display_name
            avatar = member.display_avatar.url
        except AttributeError:
            name = member.name
            avatar = member.display_avatar.url if hasattr(member, "display_avatar") else None

        base_embed.set_author(name=name, icon_url=avatar)

        # Copy for user and logs
        user_embed = base_embed.copy()
        log_embed = base_embed.copy()

        # Appeal info for bans
        if infraction.actiontype in {"ban", "force-ban"}:
            user_embed.add_field(
                name="Appeal",
                value="If you wish to appeal your ban, you may do so by joining the following server: https://discord.gg/RHx7deYQ3q",
                inline=False
            )

        # Try DM
        dm_success = True
        try:
            await member.send(embed=user_embed)
        except Forbidden:
            dm_success = False
            user_embed.set_footer(text=f"User ID: {getattr(member, 'id', 'unknown')} | Could not DM.")

        # Logs channel
        logs_channel = nextcord.utils.get(interaction.guild.text_channels, name="logs")
        if logs_channel:
            log_embed.add_field(
                name="Responsible Moderator:",
                value=f"{infraction.moderator.display_name} ({infraction.moderator.mention})",
                inline=False,
            )
            log_embed.add_field(
                name="User ID:",
                value=f"<@{getattr(member, 'id', 'unknown')}> (`{getattr(member, 'id', 'unknown')}`)",
                inline=False,
            )
            log_embed.add_field(
                name="DM Status:",
                value="✅ DM sent" if dm_success else "❌ Could not DM",
                inline=False
            )
            try:
                await logs_channel.send(embed=log_embed)
            except Forbidden:
                print("Failed to send to logs channel.")
        else:
            print(f"Logs channel 'logs' not found.")




            
    @slash_command(name="warn", description="Warn members of rule-breaking behavior.", default_member_permissions=Permissions(moderate_members=True), guild_ids=COMMAND_GUILD_IDS)
    async def warn(self, inter: Interaction, member: Member, reason: str = SlashOption(description="Reason for warn", required=True)):
        # Create the infraction without duration and attachment_url
        warning = Infraction(
            actiontype="warn",
            reason=reason,
            moderator=inter.user,
            actiontime=datetime.now(timezone.utc)
        )

        # Add infraction to the database
        await self.bot.db.base_db.add_infraction(member.id, warning)

        # Send warning embed
        warn_embed = Embed(
            title="Member Warned!",
            description=f"{member.mention} has been warned.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("yellow", Color.yellow()),
            timestamp=warning.actiontime
        )
        warn_embed.set_footer(text=f"{inter.user.display_name} successfully warned.", icon_url=inter.user.display_avatar.url)
        await inter.response.send_message(embed=warn_embed)

        # Send the infraction response to the logs channel
        await self.infraction_response(inter, member=member, infraction=warning)


    @slash_command(
        name="wm",
        description="Mute and add infraction points to a member.",
        default_member_permissions=Permissions(moderate_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def wm(
        self,
        interaction: Interaction,
        member: Member,
        duration: str = SlashOption(
            name="duration",
            description="Mute duration. Format: 5h9m2s",
            required=True
        ),
        reason: str = SlashOption(
            description="Reason for the mute",
            required=True
        ),
        attachment: Attachment = None,
    ):
        duration_seconds = convert_time(duration)

        if isinstance(duration_seconds, str):
            await interaction.response.send_message(duration_seconds, ephemeral=True)
            return

        time_until = timedelta(seconds=duration_seconds)

        # Defer interaction immediately without follow-up message
        await interaction.response.defer(ephemeral=False)

        # Apply the mute
        await member.timeout(timeout=time_until, reason=reason)

        # Create the Infraction object
        mute = Infraction(
            actiontype="mute",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(timezone.utc),
            duration=duration_seconds,
            attachment_url=attachment.proxy_url if attachment else None
        )

        # ✅ Add the infraction to the database BEFORE sending infraction response
        await self.bot.db.base_db.add_infraction(member.id, mute)
        await self.bot.db.emergency.set_cooldown(member.id, minutes=60 * 24)
        # Calculate unmute time
        unmute_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

        # Send the infraction response (DM user, log to #logs, trigger 30+ update)
        await self.infraction_response(interaction, member=member, infraction=mute)

        # Get updated infraction points to show in confirmation
        inf_points = await self.bot.db.base_db.get_inf_points(member.id)

        # Final confirmation embed
        mute_embed = Embed(
            title="Member Muted!",
            description=(
                f"{member.mention} has been muted.\n\n"
                f"**Reason:**\n{reason}\n\n"
                f"**Will be unmuted at:** <t:{int(unmute_time.timestamp())}:f> (<t:{int(unmute_time.timestamp())}:R>)"
            ),
            color=self.bot.colors.get("light_orange", Color.orange()),
            timestamp=datetime.now(timezone.utc)
        )

        # Add infraction point summary below everything
        mute_embed.add_field(
            name="Infraction Points",
            value=f"`{inf_points}` total infraction point(s).",
            inline=False
        )

        mute_embed.set_footer(text=f"Muted by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        # Send the embed publicly
        await interaction.followup.send(embed=mute_embed)


        if inf_points>= 30:
            updates_channel = nextcord.utils.get(interaction.guild.text_channels, name="important-updates")
            if updates_channel:
                mod_role = nextcord.utils.get(interaction.guild.roles, name="Chat Moderator")
                await updates_channel.send(
                    content=mod_role.mention if mod_role else None,
                    embed=Embed(
                        title="Member has reached 30 infraction points!",
                        description=f"{member.mention}  has `{inf_points}` infraction points and should be reviewed for a ban.",
                        color=self.bot.colors.get("red")
                    )
                )

    @slash_command(
        name="mute",
        description="Mute a member without adding infraction points.",
        default_member_permissions=Permissions(moderate_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def mute(
        self,
        interaction: Interaction,
        member: Member,
        duration: str = SlashOption(
            name="duration",
            description="Mute duration. Format: 5h9m2s",
            required=True
        ),
        reason: str = SlashOption(
            description="Reason for the mute",
            required=True
        ),
    ):
        duration_seconds = convert_time(duration)

        if isinstance(duration_seconds, str):
            await interaction.response.send_message(duration_seconds, ephemeral=True)
            return

        time_until = timedelta(seconds=duration_seconds)

        # Acknowledge the interaction quickly
        await interaction.response.send_message(f"Muting {member.display_name}...", ephemeral=False)

        # Apply the mute
        await member.timeout(timeout=time_until, reason=reason)

        mute = Infraction(
            actiontype="pseudo-mute",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(timezone.utc),
            duration=duration_seconds
        )

        # Send the infraction response
        await self.infraction_response(interaction, member=member, infraction=mute)
        # Calculate unmute time
        unmute_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

        # Send embedded message about the mute
        mute_embed = Embed(
            title="Member Muted!",
            description=f"{member.mention} has been muted.\n\n**Reason:**\n{reason}\n\n**Will be unmuted at:** <t:{int(unmute_time.timestamp())}:f> (<t:{int(unmute_time.timestamp())}:R>)",
            color=self.bot.colors.get("light_orange", Color.orange()),  # Use your defined color or light orange
            timestamp=datetime.now(timezone.utc)
        )

        mute_embed.set_footer(text=f"Muted by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        await interaction.followup.send(embed=mute_embed)
    @slash_command(
        name="unmute",
        description="Unmute a member.",
        default_member_permissions=Permissions(moderate_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def unmute(
        self,
        interaction: Interaction,
        member: Member,
        reason: str = SlashOption(description="Reason for unmute", required=True)
    ):
        await interaction.response.defer(ephemeral=False)  # Make response visible to everyone

        # Remove the timeout (unmute) the member
        await member.timeout(None, reason=reason)

        await self.bot.db.emergency.clear_cooldown(member.id)

        # Create an infraction object for logging
        unmute = Infraction(
            actiontype="unmute",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(timezone.utc)
        )

        # Send infraction response to logs channel
        await self.infraction_response(interaction, member=member, infraction=unmute)

        # Create the embed for the unmute message
        unmute_embed = Embed(
            title="Member Unmuted!",
            description=f"{member.mention} has been unmuted.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("green", Color.green()),  # Use your defined color or default green
            timestamp=unmute.actiontime
        )

        # Set the footer with moderator information
        unmute_embed.set_footer(text=f"Unmuted by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        # Send the embed as a follow-up message
        await interaction.followup.send(embed=unmute_embed)


    @slash_command(
        name="kick",
        description="Kick members for rule-breaking behavior.",
        default_member_permissions=Permissions(kick_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def kick(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        attachment: Attachment = None,
    ):
        # Make command visible to everyone (or at least the moderator)
        await interaction.response.defer(ephemeral=False)

        # Create infraction object
        kick_inf = Infraction(
            actiontype="kick",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(timezone.utc),
            attachment_url=attachment.proxy_url if attachment else None
        )

        # Try DM first
        try:
            dm_embed = Embed(
                title="You have been kicked!",
                description=f"**Reason:**\n{reason}",
                color=self.bot.colors.get("dark_orange", nextcord.Color.orange()),
                timestamp=kick_inf.actiontime
            )
            if attachment:
                dm_embed.set_image(url=attachment.proxy_url)
            await member.send(embed=dm_embed)
        except Forbidden:
            pass

        # Kick the user
        try:
            await member.kick(reason=reason)
        except Forbidden:
            return await interaction.followup.send("❌ I do not have permission to kick this user.", ephemeral=True)
        except nextcord.HTTPException:
            return await interaction.followup.send("❌ Failed to kick user.", ephemeral=True)

        # Log embed (same style as ban)
        kick_embed = Embed(
            title="Member Kicked!",
            description=f"{member.mention} has been kicked.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("dark_orange", nextcord.Color.orange()),
            timestamp=kick_inf.actiontime
        )
        if attachment:
            kick_embed.set_image(url=attachment.proxy_url)
        kick_embed.set_footer(text=f"Kicked by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        # Send public confirmation to the mod/server
        await interaction.followup.send(embed=kick_embed)

        # Send log to logs channel
        logs_channel = nextcord.utils.get(interaction.guild.text_channels, name="logs")
        if logs_channel:
            log_embed = Embed(
                title="Kick Logged",
                description=f"User: {member.mention} (`{member.id}`)\nModerator: {interaction.user.mention}",
                color=self.bot.colors.get("dark_orange", nextcord.Color.orange()),
                timestamp=kick_inf.actiontime
            )
            log_embed.add_field(name="Reason", value=reason, inline=False)
            if attachment:
                log_embed.set_image(url=attachment.proxy_url)
            await logs_channel.send(embed=log_embed)


    @slash_command(
        name="ban",
        description="Ban members for rule-breaking behavior.",
        default_member_permissions=Permissions(ban_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def ban(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        attachment: Attachment = None,
    ):
        await interaction.response.defer(ephemeral=False)

        ban_inf = Infraction(
            actiontype="ban",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(timezone.utc),
            attachment_url=attachment.proxy_url if attachment else None
        )
        await self.bot.db.base_db.add_infraction(member.id, ban_inf)
        # ✅ DM the user and log BEFORE banning (so the DM goes through)
        await self.infraction_response(interaction, member=member, infraction=ban_inf)

        # 🚫 Then actually ban them
        await member.ban(reason=reason)

        ban_embed = Embed(
            title="Member Banned!",
            description=f"{member.mention} has been banned.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("red", Color.red()),
            timestamp=ban_inf.actiontime
        )

        if attachment:
            ban_embed.set_image(url=attachment.proxy_url)

        ban_embed.set_footer(text=f"Banned by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=ban_embed)



    @slash_command(
        name="force-ban",
        description="Force-ban a user by ID or mention, even if they are not in the server.",
        default_member_permissions=Permissions(ban_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def forceban(
        self,
        interaction: Interaction,
        user: Union[Member, nextcord.User],
        reason: str,
        attachment: Attachment = None,
    ):


        forceban_inf = Infraction(
            actiontype="force-ban",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(timezone.utc),
            attachment_url=attachment.proxy_url if attachment else None
        )
        await self.bot.db.base_db.add_infraction(user.id, forceban_inf)
        await interaction.response.defer(ephemeral=False)


        # ✅ DM first
        await self.infraction_response(interaction, member=user, infraction=forceban_inf)

        # 🚫 Ban user by ID (works even if they left)
        try:
            await interaction.guild.ban(user=user, reason=reason, delete_message_seconds=604800)
        except Forbidden:
            return await interaction.followup.send("❌ I don't have permission to ban this user.", ephemeral=True)
        except nextcord.HTTPException:
            return await interaction.followup.send("❌ Failed to ban user.", ephemeral=True)

        embed = Embed(
            title="Member Force-Banned!",
            description=f"{user.mention} has been force-banned.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("red", Color.red()),
            timestamp=forceban_inf.actiontime
        )
        if attachment:
            embed.set_image(url=attachment.proxy_url)
        embed.set_footer(text=f"Force-banned by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    



    @slash_command(
        name="unban",
        description="Unban a previously banned user by ID or mention.",
        default_member_permissions=Permissions(ban_members=True),
        guild_ids=COMMAND_GUILD_IDS
    )
    async def unban(
        self,
        interaction: Interaction,
        user: nextcord.User,  # Use User only, since Member won't exist
        reason: str = SlashOption(description="Reason for unban", required=True)
    ):
        await interaction.response.defer(ephemeral=False)

        # ✅ DM before unban
        unban_inf = Infraction(
            actiontype="unban",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(timezone.utc)
        )
        await self.infraction_response(interaction, member=user, infraction=unban_inf)

        # Attempt to unban
        try:
            await interaction.guild.unban(user, reason=reason)
        except nextcord.NotFound:
            return await interaction.followup.send(f"❌ User `{user}` is not banned or ID is incorrect.", ephemeral=True)
        except Forbidden:
            return await interaction.followup.send("❌ I do not have permission to unban this user.", ephemeral=True)

        embed = Embed(
            title="Member Unbanned!",
            description=f"{user.mention} has been unbanned.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("green", Color.green()),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Unbanned by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @slash_command(
        name="note",
        description="Add an internal moderation note to a user",
        guild_ids=COMMAND_GUILD_IDS,
        default_member_permissions=Permissions(moderate_members=True),
    )
    async def note(
        self,
        inter: Interaction,
        member: Member,
        note: str = SlashOption(
            description="Internal note (not visible to the user)",
            required=True,
        ),
    ):
        if not self.has_mod_role(inter.user):
            return await inter.response.send_message(
                "You do not have permission to use this command.",
                ephemeral=True
            )

        inf = Infraction(
            actiontype="note",
            reason=note,
            moderator=inter.user,
            actiontime=datetime.now(timezone.utc),
            duration=None,
            attachment_url=None,
        )

        await self.bot.db.base_db.add_infraction(member.id, inf)

        embed = Embed(
            title="Note Added",
            description=f"**User:** {member.mention}\n**Note:**\n{note}",
            color=0x9B59B6,  # 💜 purple
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text=f"Added by {inter.user.display_name}")

        await inter.response.send_message(embed=embed)

    def has_exam_moderator_role(self, member: Member) -> bool:
        return any(role.name == "Exam Moderator" for role in member.roles)

    def restricted_collection(self):
        return self.bot.db.base_db.database["temporary_restrictions"]

    async def save_temporary_restriction(
        self,
        *,
        guild_id: int,
        user_id: int,
        role_id: int,
        moderator_id: int,
        expires_at: int,
    ) -> None:
        await self.restricted_collection().update_one(
            {
                "guild_id": guild_id,
                "user_id": user_id,
            },
            {
                "$set": {
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "role_id": role_id,
                    "moderator_id": moderator_id,
                    "expires_at": expires_at,
                    "updated_at": int(datetime.now(timezone.utc).timestamp()),
                }
            },
            upsert=True,
        )

    async def delete_temporary_restriction(self, guild_id: int, user_id: int) -> None:
        await self.restricted_collection().delete_one(
            {
                "guild_id": guild_id,
                "user_id": user_id,
            }
        )

    async def remove_restricted_role(self, guild_id: int, user_id: int) -> None:
        """
        Remove Restricted role after the saved 48-hour timer expires.
        This checks Mongo first, so old timers will not remove newer restrictions.
        """
        try:
            doc = await self.restricted_collection().find_one(
                {
                    "guild_id": guild_id,
                    "user_id": user_id,
                }
            )

            if not doc:
                return

            now_ts = int(datetime.now(timezone.utc).timestamp())
            expires_at = int(doc.get("expires_at", 0))

            if now_ts < expires_at:
                remaining = expires_at - now_ts
                self.bot.loop.call_later(
                    remaining,
                    lambda: asyncio.create_task(
                        self.remove_restricted_role(guild_id, user_id)
                    ),
                )
                return

            guild = self.bot.get_guild(guild_id)

            if guild is None:
                try:
                    guild = await self.bot.fetch_guild(guild_id)
                except Exception:
                    return

            role_id = int(doc.get("role_id", 0))
            restricted_role = guild.get_role(role_id)

            if restricted_role is None:
                restricted_role = nextcord.utils.get(guild.roles, name="Restricted")

            if restricted_role is None:
                await self.delete_temporary_restriction(guild_id, user_id)
                return

            try:
                member = guild.get_member(user_id)

                if member is None:
                    member = await guild.fetch_member(user_id)

            except nextcord.NotFound:
                await self.delete_temporary_restriction(guild_id, user_id)
                return

            except Exception:
                return

            if restricted_role in member.roles:
                await member.remove_roles(
                    restricted_role,
                    reason="Automatic Restricted role removal after 48 hours.",
                )

            await self.delete_temporary_restriction(guild_id, user_id)

            logs_channel = nextcord.utils.get(guild.text_channels, name="logs")

            if logs_channel:
                embed = Embed(
                    title="Member Restriction Expired!",
                    description=(
                        f"{member.mention} no longer has the **Restricted** role.\n\n"
                        "**Reason:**\n48 hour restriction expired."
                    ),
                    color=self.bot.colors.get("green", Color.green()),
                    timestamp=datetime.now(timezone.utc),
                )
                embed.set_footer(text="Automatic restriction cleanup")
                await logs_channel.send(embed=embed)

        except Exception as exc:
            print(f"[Restrict] Failed to remove Restricted role for {user_id}: {exc}")

    @tasks.loop(minutes=5)
    async def restricted_cleanup_loop(self):
        """
        Backup cleanup.

        This makes restrictions survive bot restarts.
        Even if call_later gets lost from a restart, this loop checks Mongo.
        """
        try:
            now_ts = int(datetime.now(timezone.utc).timestamp())

            cursor = self.restricted_collection().find(
                {
                    "expires_at": {
                        "$lte": now_ts,
                    }
                }
            )

            async for doc in cursor:
                guild_id = int(doc.get("guild_id"))
                user_id = int(doc.get("user_id"))

                await self.remove_restricted_role(guild_id, user_id)

        except Exception as exc:
            print(f"[Restrict Cleanup] Loop failed: {exc}")

    @restricted_cleanup_loop.before_loop
    async def before_restricted_cleanup_loop(self):
        await self.bot.wait_until_ready()

    @slash_command(
        name="restrict",
        description="Give a member the Restricted role for 48 hours.",
        guild_ids=COMMAND_GUILD_IDS,
    )
    async def restrict(
        self,
        inter: Interaction,
        user: Member = SlashOption(
            name="user",
            description="The user to restrict.",
            required=True,
        ),
    ):
        # Permission checks FIRST.
        # This keeps denial messages private.
        if not isinstance(inter.user, Member):
            return await inter.response.send_message(
                "This command can only be used in the server.",
                ephemeral=True,
            )

        if not self.has_exam_moderator_role(inter.user):
            return await inter.response.send_message(
                "You need the **Exam Moderator** role to use this command.",
                ephemeral=True,
            )

        # Only defer publicly after the user is allowed to use the command.
        await inter.response.defer(ephemeral=False)

        restricted_role = nextcord.utils.get(inter.guild.roles, name="Restricted")

        if restricted_role is None:
            return await inter.followup.send(
                "I could not find a role called **Restricted**.",
                ephemeral=True,
            )

        bot_member = inter.guild.me

        if bot_member is None:
            return await inter.followup.send(
                "I could not check my own server permissions.",
                ephemeral=True,
            )

        if restricted_role >= bot_member.top_role:
            return await inter.followup.send(
                "I cannot assign the **Restricted** role because it is higher than or equal to my highest role.",
                ephemeral=True,
            )

        if user.top_role >= bot_member.top_role:
            return await inter.followup.send(
                "I cannot restrict this user because their highest role is higher than or equal to mine.",
                ephemeral=True,
            )

        duration_seconds = 60 * 60 * 48
        restricted_end = int(datetime.now(timezone.utc).timestamp()) + duration_seconds
        already_restricted = restricted_role in user.roles

        dm_success = True

        try:
            if not already_restricted:
                await user.add_roles(
                    restricted_role,
                    reason=None,
                )

            await self.save_temporary_restriction(
                guild_id=inter.guild.id,
                user_id=user.id,
                role_id=restricted_role.id,
                moderator_id=inter.user.id,
                expires_at=restricted_end,
            )

            self.bot.loop.call_later(
                duration_seconds,
                lambda: asyncio.create_task(
                    self.remove_restricted_role(inter.guild.id, user.id)
                ),
            )

            try:
                dm_embed = Embed(
                    title="Your account is under review",
                    description=(
                        "You have been restricted from the server because your account "
                        "is currently under review for a possible violation of an AP exam security-related rule. \n\n"
                        "This review may last up to 48 hours."
                    ),
                    color=self.bot.colors.get("red", Color.red()),
                    timestamp=datetime.now(timezone.utc),
                )
                dm_embed.set_footer(text="AP Students Moderation")

                await user.send(embed=dm_embed)

            except Forbidden:
                dm_success = False
            except Exception:
                dm_success = False

        except Forbidden:
            return await inter.followup.send(
                "I do not have permission to give this user the **Restricted** role.",
                ephemeral=True,
            )

        except nextcord.HTTPException as exc:
            return await inter.followup.send(
                f"Failed to restrict this user: `{exc}`",
                ephemeral=True,
            )

        except Exception as exc:
            return await inter.followup.send(
                f"Failed to save the temporary restriction: `{exc}`",
                ephemeral=True,
            )

        if already_restricted:
            title = "Member Restriction Updated!"
        else:
            title = "Member Restricted!"

        restrict_embed = Embed(
            title=title,
            description=(
                f"{user.mention} has been given the **Restricted** role.\n\n"
                f"**Duration:**\n48 hours\n\n"
                f"**Restriction ends:** <t:{restricted_end}:f> (<t:{restricted_end}:R>)"
            ),
            color=self.bot.colors.get("red", Color.red()),
            timestamp=datetime.now(timezone.utc),
        )

        restrict_embed.add_field(
            name="DM Status",
            value="✅ DM sent" if dm_success else "❌ Could not DM",
            inline=False,
        )

        restrict_embed.set_footer(
            text=f"Restricted by {inter.user.display_name}",
            icon_url=inter.user.display_avatar.url,
        )

        await inter.followup.send(embed=restrict_embed)

        logs_channel = nextcord.utils.get(inter.guild.text_channels, name="logs")

        if logs_channel:
            log_embed = Embed(
                title="Restriction Logged",
                description=(
                    f"User: {user.mention} (`{user.id}`)\n"
                    f"Moderator: {inter.user.mention}\n"
                    f"Expires: <t:{restricted_end}:f> (<t:{restricted_end}:R>)\n"
                    f"DM Status: {'✅ DM sent' if dm_success else '❌ Could not DM'}"
                ),
                color=self.bot.colors.get("red", Color.red()),
                timestamp=datetime.now(timezone.utc),
            )

            await logs_channel.send(embed=log_embed)



async def setup(bot: APBot) -> None:
    bot.add_cog(ModerationCommands(bot))


