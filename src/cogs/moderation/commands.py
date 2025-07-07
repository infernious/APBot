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

from nextcord.ext import commands
import asyncio
from datetime import datetime, timedelta
from typing import Union, Optional
from bot_base import APBot
from cogs.utils import convert_time

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

    @slash_command(
        name="warnchannel",
        description="Send a warning to a channel and temporarily modify permissions",
        default_member_permissions=Permissions(moderate_members=True),
    )
    async def warnchannel(
        self,
        inter: Interaction,
        reason: str = SlashOption(description="The reason for the warning", required=False)
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
            "unban": ("unban", self.bot.colors.get("green")),
        }

        infraction_name, color = infraction_details.get(infraction.actiontype, ("Infraction", nextcord.Color.default()))

        # Base embed (for both user and logs)
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

            if infraction.actiontype == "mute":
                # Determine infraction points based on duration
                if infraction.duration < 6 * 3600:
                    change = 5
                elif infraction.duration < 12 * 3600:
                    change = 10
                elif infraction.duration < 24 * 3600:
                    change = 15
                elif infraction.duration >= 24 * 3600:
                    change = 20
                else:
                    change = 0

                inf_points = await self.bot.db.base_db.add_inf_points(member.id, change)
                if inf_points is not None:
                    base_embed.add_field(
                        name="**Infraction Points:**",
                        value=f"`{inf_points}` (+{change})",
                        inline=False
                    )

                else:
                    base_embed.add_field(
                        name="**Infraction Points:**",
                        value="Failed to update infraction points in the database.",
                        inline=False
                    )

        if infraction.attachment_url:
            base_embed.set_image(url=infraction.attachment_url)

        base_embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)

        # Make a separate copy for user and logs
        user_embed = base_embed.copy()
        log_embed = base_embed.copy()

        # Only user gets appeal info
        if infraction.actiontype in {"ban", "force-ban"}:
            user_embed.add_field(
                name="Appeal",
                value="If you wish to appeal your ban, you may do so by joining the following server: https://discord.gg/RHx7deYQ3q",
                inline=False
            )

        # Try to DM the user
        try:
            await member.send(embed=user_embed)
        except Forbidden:
            user_embed.set_footer(text=f"User ID: {member.id} | Could not DM.")

        # Send log embed to logs channel
        logs_channel_name = "logs"
        logs_channel = nextcord.utils.get(interaction.guild.text_channels, name=logs_channel_name)
        if logs_channel:
            log_embed.add_field(
                name="Responsible Moderator:",
                value=f"{infraction.moderator.display_name} ({infraction.moderator.mention})",
                inline=False,
            )
            log_embed.add_field(
                name="User ID:",
                value=f"<@{member.id}> (`{member.id}`)",  # This will ping the user and show their ID in code format
                inline=False,
            )
            try:
                await logs_channel.send(embed=log_embed)
            except Forbidden:
                print("Failed to send to logs channel.")
        else:
            print(f"Logs channel '{logs_channel_name}' not found.")



            
    @slash_command(name="warn", description="Warn members of rule-breaking behavior.", default_member_permissions=Permissions(moderate_members=True))
    async def warn(self, inter: Interaction, member: Member, reason: str = SlashOption(description="Reason for warn", required=True)):
        # Create the infraction without duration and attachment_url
        warning = Infraction(
            actiontype="warn",
            reason=reason,
            moderator=inter.user,
            actiontime=datetime.now()
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
        await self.infraction_response( member=member, infraction=warning)


    @slash_command(
        name="wm",
        description="Mute and add infraction points to a member.",
        default_member_permissions=Permissions(moderate_members=True),
    )
    async def wm(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        duration: str = SlashOption(name="duration", description="Mute duration. Format: 5h9m2s", required=True),
        attachment: Attachment = None,
    ):
        duration_seconds: int = convert_time(duration)
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
            actiontime=datetime.now(),
            duration=duration_seconds,
            attachment_url=attachment.proxy_url if attachment else None
        )

        # ✅ Add the infraction to the database BEFORE sending infraction response
        await self.bot.db.base_db.add_infraction(member.id, mute)

        # Calculate unmute time
        unmute_time = datetime.now() + timedelta(seconds=duration_seconds)

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
            timestamp=datetime.now()
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
    )
    async def mute(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        duration: str = SlashOption(name="duration", description="Mute duration. Format: 5h9m2s", required=True),
    ):
        duration_seconds: int = convert_time(duration)
        time_until = timedelta(seconds=duration_seconds)

        # Acknowledge the interaction quickly
        await interaction.response.send_message(f"Muting {member.display_name}...", ephemeral=False)

        # Apply the mute
        await member.timeout(timeout=time_until, reason=reason)

        mute = Infraction(
            actiontype="pseudo-mute",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(),
            duration=duration_seconds
        )

        # Send the infraction response
        await self.infraction_response(interaction, member=member, infraction=mute)

        # Calculate unmute time
        unmute_time = datetime.now() + timedelta(seconds=duration_seconds)

        # Send embedded message about the mute
        mute_embed = Embed(
            title="Member Muted!",
            description=f"{member.mention} has been muted.\n\n**Reason:**\n{reason}\n\n**Will be unmuted at:** <t:{int(unmute_time.timestamp())}:f> (<t:{int(unmute_time.timestamp())}:R>)",
            color=self.bot.colors.get("light_orange", Color.orange()),  # Use your defined color or light orange
            timestamp=datetime.now()
        )

        mute_embed.set_footer(text=f"Muted by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        await interaction.followup.send(embed=mute_embed)
    @slash_command(
        name="unmute",
        description="Unmute a member.",
        default_member_permissions=Permissions(moderate_members=True),
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

        # Create an infraction object for logging
        unmute = Infraction(
            actiontype="unmute",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now()
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
    )
    async def kick(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        attachment: Attachment = None,
    ):
        await interaction.response.defer(ephemeral=True)
        await member.kick(reason=reason)

        kick = Infraction(
            actiontype="kick",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(),
            attachment_url=attachment.proxy_url if attachment else None
        )

        await self.infraction_response(
           interaction, member=member, infraction=kick
        )

        await interaction.followup.send(
            f"`{member.display_name} successfully kicked.`", ephemeral=True
        )

    @slash_command(
        name="ban",
        description="Ban members for rule-breaking behavior.",
        default_member_permissions=Permissions(ban_members=True),
    )
    async def ban(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        attachment: Attachment = None,
    ):
        await interaction.response.defer(ephemeral=False)

        await member.ban(reason=reason)

        ban = Infraction(
            actiontype="ban",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(),
            attachment_url=attachment.proxy_url if attachment else None
        )

        await self.infraction_response(interaction, member=member, infraction=ban)

        ban_embed = Embed(
            title="Member Banned!",
            description=f"{member.mention} has been banned.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("red", Color.red()),
            timestamp=ban.actiontime
        )

        if attachment:
            ban_embed.set_image(url=attachment.proxy_url)

        ban_embed.set_footer(text=f"Banned by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=ban_embed)


    @slash_command(
        name="force-ban",
        description="Force-ban a user by ID or mention, even if they are not in the server.",
        default_member_permissions=Permissions(ban_members=True),
    )
    async def forceban(
        self,
        interaction: Interaction,
        user: Union[Member, nextcord.User],
        reason: str,
        attachment: Attachment = None,
    ):
        await interaction.response.defer(ephemeral=False)

        # Ban using guild method to support users not in server
        await interaction.guild.ban(user=user, reason=reason, delete_message_seconds=604800)

        forceban = Infraction(
            actiontype="force-ban",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(),
            attachment_url=attachment.proxy_url if attachment else None
        )

        await self.infraction_response(interaction, member=user, infraction=forceban)

        embed = Embed(
            title="Member Force-Banned!",
            description=f"{user.mention} has been force-banned.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("red", Color.red()),
            timestamp=forceban.actiontime
        )

        if attachment:
            embed.set_image(url=attachment.proxy_url)

        embed.set_footer(text=f"Force-banned by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed) 



    @slash_command(
        name="unban",
        description="Unban a previously banned user by ID or mention.",
        default_member_permissions=Permissions(ban_members=True),
    )
    async def unban(
        self,
        interaction: Interaction,
        user: Union[Member, nextcord.User],
        reason: str = SlashOption(description="Reason for unban", required=True)
    ):
        await interaction.response.defer(ephemeral=False)

        # Attempt to unban the user
        try:
            await interaction.guild.unban(user, reason=reason)
        except nextcord.NotFound:
            await interaction.followup.send(
                f"❌ User `{user}` is not banned or the ID is incorrect.",
                ephemeral=True
            )
            return
        except nextcord.Forbidden:
            await interaction.followup.send(
                "❌ I do not have permission to unban this user.",
                ephemeral=True
            )
            return

        # Create an Infraction instance for logging
        unban = Infraction(
            actiontype="unban",  # Technically it's an "unban", but for consistency in your embed logic
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now()
        )

        # Send the infraction log to logs channel
        await self.infraction_response(interaction, member=user, infraction=unban)

        # Prepare confirmation embed
        embed = Embed(
            title="Member Unbanned!",
            description=f"{user.mention} has been unbanned.\n\n**Reason:**\n{reason}",
            color=self.bot.colors.get("green", Color.green()),
            timestamp=datetime.now()
        )

        embed.set_footer(text=f"Unbanned by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        await interaction.followup.send(embed=embed)



async def setup(bot: APBot) -> None:
    bot.add_cog(ModerationCommands(bot))
