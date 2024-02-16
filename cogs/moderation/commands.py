import time
from datetime import datetime

from nextcord import (
    slash_command,
    message_command,
    Permissions,
    Interaction,
    Embed,
    Member,
    Object,
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
from typing import Union
from cogs.utils import convert_time


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
        channel: TextChannel = SlashOption(
            description="The channel to send the warning to", required=True
        ),
        reason: str = SlashOption(
            description="The reason for the warning", required=True
        ),
    ):
        """
        Sends a warning message to a specified channel, disables @everyone's message permissions for 10 seconds,
        and then sets a 15-second slowmode in the channel.
        """
        await inter.response.defer(ephemeral=True)
        
        resp = await inter.send("Processing the warning...", ephemeral=True)

        # Send an embed with the warning reason
        embed = Embed(
            title="This channel has been warned!",
            description=f"⚠️ {reason}",
            color=Color.red(),
        )
        embed.set_footer(text="This channel will be unlocked in 1 minute.")
        await channel.send(embed=embed)

        # Temporarily change permissions
        await channel.set_permissions(inter.guild.default_role, send_messages=False)
        await resp.edit(f"Warning sent to {channel.mention}.")

        # Unlock channel, set slowmode, and revert permissions
        await asyncio.sleep(60)  # Wait for 60 seconds
        await channel.edit(slowmode_delay=15)
        await channel.set_permissions(inter.guild.default_role, send_messages=True)
        await resp.edit(f"Warning sent to {channel.mention} and slowmode is enabled.")

    async def infraction_response(
        self, member: Member, moderator: Member, infraction: dict
    ):
        match infraction["type"]:
            # /warn
            case "warn":
                color = self.bot.colors.get("yellow")
                infraction_name = "Warning"
            # /wm (NOT /mute)
            case "mute":
                color = self.bot.colors.get("orange")
                infraction_name = "Mute"
            # /mute (NOT /wm) (shitty i know)
            case "pseudo-mute":
                color = self.bot.colors.get("light_orange")
                infraction_name = "Mute"
            case "unmute":
                color = self.bot.colors.get("green")
                infraction_name = "Unmute"
            # /kick
            case "kick":
                color = self.bot.colors.get("dark_orange")
                infraction_name = "Kick"
            # /ban
            case "ban":
                color = self.bot.colors.get("red")
                infraction_name = "Ban"
            # /forceban
            case "force-ban":
                color = self.bot.colors.get("red")
                infraction_name = "Force-Ban"

        infraction_embed = (
            Embed(
                title="",
                color=color,
            )
            .add_field(
                name=f"Infraction: {infraction_name}",
                value=f"Reason: {infraction['reason']}",
                inline=False,
            )
            .set_footer(text=f"User ID: {member.id}")
            .timestamp(datetime.datetime.now())
        )

        if "duration" in infraction:
            mute_end = int(time.time()) + infraction["duration"]
            infraction_embed.add_field(
                name="Unmute:",
                value=f"<t:{mute_end}:f> (<t:{mute_end}:R>)",
                inline=False,
            )

            if infraction["type"] == "mute":
                if infraction["duration"] >= 60 * 60 * 12:
                    change = 15
                elif infraction["duration"] >= 60 * 60 * 6:
                    change = 10
                else:
                    change = 5
                inf_points = await self.bot.db.add_inf_points(member.id, change)

                infraction_embed.add_field(
                    name="Infraction Points:",
                    value=f"`{inf_points}` (+{change} from previous infraction points)",
                )

        if "attachment" in infraction:
            infraction_embed.set_image(infraction["attachment"])

        try:
            await member.send(infraction_embed)
        except Forbidden:
            infraction_embed.set_footer(text=f"User ID: {member.id} | Could not DM.")

        infraction_embed.name = (member.display_name,)
        infraction_embed.icon_url = member.display_avatar.url
        infraction_embed.add_field(
            name="Responsible Moderator:",
            value=f"{moderator.display_name} ({moderator.mention})",
            inline=False,
        )

        logs: TextChannel = await self.bot.fetch_channel(
            self.bot.config.get("logs_channel")
        )
        await logs.send(embed=infraction_embed)

        if infraction["type"] == "pseudo-mute":
            return

        await self.bot.db.add_infraction(member.id, infraction)

    @slash_command(
        name="warn",
        description="Warn members of rule-breaking behavior.",
        default_member_permissions=Permissions(moderate_members=True),
    )
    async def warn(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        attachment: Attachment = None,
    ):
        await interaction.response.defer(ephemeral=True)

        warning = {
            "type": "warn",
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name})",
            "date": datetime.datetime.now(),
        }

        if attachment:
            warning["attachment"] = attachment.proxy_url

        await self.infraction_response(
            member=member, moderator=interaction.user, infraction=warning
        )

        await interaction.followup.send(
            f"`{member.display_name} successfully warned.`", ephemeral=True
        )

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
        duration: str = SlashOption(
            name="duration",
            choices={
                "3 hours (minor offense)": "3h",
                "6 hours (moderate offense)": "6h",
                "12 hours (repeated minor/moderate offenses)": "12h",
                "24 hours (major / repeated moderate offense)": "24h",
                "48 hours (major / repeated moderate offense)": "48h",
            },
            required=True,
        ),
        attachment: Attachment = None,
    ):
        duration: Union[str, int] = convert_time(duration)
        time_until = datetime.timedelta(seconds=duration)
        await member.timeout(timeout=time_until, reason=reason)

        mute = {
            "type": "mute",
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
        name="mute",
        description="Mute a member without adding infraction points.",
        default_member_permissions=Permissions(moderate_members=True),
    )
    async def mute(
        self,
        interaction: Interaction,
        member: Member,
        reason: str,
        duration: str = SlashOption(
            name="duration", description="Mute duration. Format: 5h9m2s", required=True
        ),
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

        logs: TextChannel = await self.bot.fetch_channel(
            self.bot.config.get("logs_channel")
        )
        await logs.send(embed=log_embed)

        await interaction.followup.send(
            "`Message successfully deleted!`", ephemeral=True
        )


async def setup(bot: APBot):
    bot.add_cog(ModerationCommands(bot))
