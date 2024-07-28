import time
from datetime import datetime, timedelta

from nextcord import (
    slash_command,
    message_command,
    Permissions,
    Interaction,
    Embed,
    Member,
    TextChannel,
    SlashOption,
    Attachment,
    Forbidden,
    Message,
    Color,
)
from nextcord.ext import commands
import asyncio
from bot_base import APBot
from typing import Union, Optional
from cogs.utils import convert_time

from models import Infraction


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
        """
        Sends a warning message to a specified channel, disables @everyone's message permissions for 5 minutes,
        and then sets a 15-second slowmode in the channel.
        """
        await inter.response.defer(ephemeral=True)

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

        logs_channel: TextChannel = await self.bot.getch_channel(self.bot.config.get("logs_channel"))
        if logs_channel:
            await logs_channel.send(embed=Embed(
                title=f"Channel Warn",
                description=f"Responsible Mod: {inter.user.mention}\nReason: {reason if reason else 'No Reason Given.'}",
                color=self.bot.colors.get("light_orange")
            ))

        # Unlock channel, set slowmode, and revert permissions
        await asyncio.sleep(60 * 5)  # Wait for 5 minutes
        await inter.channel.edit(slowmode_delay=15)
        await inter.channel.set_permissions(inter.guild.default_role, send_messages=True)

    async def infraction_response(self, member: Member, infraction: Infraction) -> None:
        match infraction.actiontype:
            case "warn":
                color = self.bot.colors.get("yellow")
                infraction_name = "Warning"
            case "mute": # /wm (NOT /mute)
                color = self.bot.colors.get("orange")
                infraction_name = "Mute"
            case "pseudo-mute": # /mute (NOT /wm)
                color = self.bot.colors.get("light_orange")
                infraction_name = "Mute"
            case "unmute":
                color = self.bot.colors.get("green")
                infraction_name = "Unmute"
            case "kick":
                color = self.bot.colors.get("dark_orange")
                infraction_name = "Kick"
            case "ban":
                color = self.bot.colors.get("red")
                infraction_name = "Ban"
            case "force-ban":
                color = self.bot.colors.get("red")
                infraction_name = "Force-Ban"

        infraction_embed = Embed(
            title=f"Infraction: {infraction_name}",
            description=f"Reason: {infraction.reason}",
            color=color,
            timestamp=infraction.actiontime
        )

        if infraction.duration:
            mute_end = (infraction.actiontime + timedelta(seconds=infraction.duration)).timestamp()
            infraction_embed.add_field(
                name="Unmute:",
                value=f"<t:{mute_end}:f> (<t:{mute_end}:R>)",
                inline=False,
            )

            if infraction.actiontype == "mute":
                change = 15 if infraction.duration >= 60 * 60 * 12 else (10 if infraction.duration >= 60 * 60 * 6 else 5)
                inf_points = await self.bot.db.add_inf_points(member.id, change)

                infraction_embed.add_field(
                    name="Infraction Points:",
                    value=f"`{inf_points}` (+{change} from previous infraction points)",
                )

        if infraction.attachment_url:
            infraction_embed.set_image(infraction.attachment_url)

        try:
            await member.send(infraction_embed)
        except Forbidden:
            infraction_embed.set_footer(text=f"User ID: {member.id} | Could not DM.")

        infraction_embed.name = (member.display_name,)
        infraction_embed.icon_url = member.display_avatar.url
        infraction_embed.add_field(
            name="Responsible Moderator:",
            value=f"{infraction.moderator.display_name} ({infraction.moderator.mention})",
            inline=False,
        )

        logs: TextChannel = await self.bot.getch_channel(self.bot.config.get("logs_channel"))
        await logs.send(embed=infraction_embed)

        if infraction.actiontype != "pseudo-mute":
            await self.bot.db.add_infraction(member.id, infraction)


    @slash_command(
        name="warn",
        description="Warn members of rule-breaking behavior.",
        default_member_permissions=Permissions(moderate_members=True),
    )
    async def warn(
        self,
        inter: Interaction,
        member: Member,
        reason: str = SlashOption(description="Reason for warn", required=True),
        attachment: Attachment = None,
    ):
        await inter.response.defer(ephemeral=True)

        warning = Infraction(
            actiontype="warn",
            reason=reason,
            moderator=inter.user,
            actiontime=datetime.now()
        )

        if attachment:
            warning.attachment_url = attachment.proxy_url

        await self.infraction_response(member=member, infraction=warning)

        await inter.followup.send(f"`{member.display_name} successfully warned.`", ephemeral=True)

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
        duration: Union[str, int] = convert_time(duration)
        time_until = datetime.timedelta(seconds=duration)
        await member.timeout(timeout=time_until, reason=reason)

        mute = Infraction(
            actiontype="mute",
            reason=reason,
            moderator=interaction.user,
            actiontime=datetime.now(),
            duration=duration,
            attachment_url=attachment.proxy_url if attachment else None
        )

        await self.infraction_response(
            member=member, moderator=interaction.user, infraction=mute
        )

        await interaction.followup.send(
            f"`{member.display_name} successfully muted.`", ephemeral=True
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
        attachment: Attachment = None,
    ):
        duration: Union[str, int] = convert_time(duration)
        time_until = datetime.timedelta(seconds=duration)
        await member.timeout(timeout=time_until, reason=reason)

        mute = {
            "type": "pseudo-mute",
            "duration": duration,
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name})",
            "date": datetime.datetime.now(),
        }

        if attachment:
            mute["attachment"] = attachment.proxy_url

        await self.infraction_response(
            member=member, moderator=interaction.user, infraction=mute
        )

        await interaction.followup.send(
            f"`{member.display_name} successfully muted.`", ephemeral=True
        )

    @slash_command(
        name="unmute",
        description="Unmute a member.",
        default_member_permissions=Permissions(moderate_members=True),
    )
    async def unmute(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        attachment: Attachment = None,
    ):
        await interaction.response.defer(ephemeral=True)
        await member.timeout(None, reason=reason)

        unmute = {
            "type": "unmute",
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name})",
            "date": datetime.datetime.now(),
        }

        if attachment:
            unmute["attachment"] = attachment.proxy_url

        await self.interaction_response(
            member=member, moderator=interaction.user, infraction=unmute
        )

        await interaction.followup.send(
            f"`{member.display_name} successfully unmuted.`", ephemeral=True
        )

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

        kick = {
            "type": "kick",
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name})",
            "date": datetime.datetime.now(),
        }

        if attachment:
            kick["attachment"] = attachment.proxy_url

        await self.infraction_response(
            member=member, moderator=interaction.user, infraction=kick
        )

        await interaction.guild.kick(member, reason=reason)
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
        await interaction.response.defer(ephemeral=True)

        ban = {
            "type": "ban",
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name})",
            "date": datetime.datetime.now(),
        }

        if attachment:
            ban["attachment"] = attachment.proxy_url

        await self.infraction_response(
            member=member, moderator=interaction.user, infraction=ban
        )

        await interaction.guild.ban(member, reason=reason)
        await interaction.followup.send(
            f"`{member.display_name} successfully banned.`", ephemeral=True
        )

    @message_command(
        name="Delete Message",
        default_member_permissions=Permissions(manage_messages=True),
    )
    async def delete(self, interaction: Interaction, message: Message):
        await interaction.response.defer(ephemeral=True)
        await message.delete()

        log_embed = (
            Embed(
                title="",
                color=self.bot.colors.get("orange"),
            )
            .add_field(name="Message Content:", value=message.content, inline=False)
            .add_field(
                name="Message Channel:", value=message.channel.mention, inline=False
            )
            .add_field(
                name="Responsible Moderator:",
                value=f"{interaction.user.name} ({interaction.user.mention})",
            )
            .set_author(
                name=message.author.name,
                url=f"discord://-/users/{message.author.id}",
                icon_url=message.author.avatar.url,
            )
            .timestamp(datetime.datetime.now())
        )

        if message.attachments:
            log_embed.set_image(url=message.attachments[0].proxy_url)

        logs: TextChannel = await self.bot.getch_channel(
            self.bot.config.get("logs_channel")
        )
        await logs.send(embed=log_embed)

        await interaction.followup.send(
            "`Message successfully deleted!`", ephemeral=True
        )


async def setup(bot: APBot):
    bot.add_cog(ModerationCommands(bot))