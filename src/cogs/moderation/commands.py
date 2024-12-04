import nextcord
from nextcord import app_commands
from nextcord.ext import tasks, commands

import re
import os
import time
import datetime
import motor.motor_asyncio as motor

yellow = 0xffff00
orange = 0xffa500
light_orange = 0xffa07a
dark_orange = 0xff5733
red = 0xff0000
green = 0x00ff00

time_regex = re.compile("(?:(\d{1,5})(h|s|m|d))+?")
time_dict = {"h": 3600, "hr": 3600, "hour": 3600, "hours": 3600,
             " h": 3600, " hr": 3600, " hour": 3600, " hours": 3600,
             "s": 1, "sec": 1, "seconds": 1, "second": 1,
             " s": 1, " sec": 1, " seconds": 1, " second": 1,
             "m": 60, "min": 60, "minute": 60, "minutes": 60,
             " m": 60, " min": 60, " minute": 60, " minutes": 60,
             "d": 86400, "day": 86400, "days": 86400,
             " d": 86400, " day": 86400, " days": 86400}

async def convert(argument):
    """
    Convert time string for mute commands into integer representing seconds.
    """
    args = argument.lower()
    matches = re.findall(time_regex, args)
    time = 0
    for v, k in matches:
        try:
            time += time_dict[k] * float(v)
        except KeyError:
            raise commands.BadArgument("{} is an invalid time-key! h/m/s/d are valid!".format(k))
        except ValueError:
            raise commands.BadArgument("{} is not a number!".format(v))
    return time


class BanAppeal(nextcord.ui.Modal, title="Ban Appeal"):

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    appeal = nextcord.ui.TextInput(
        label="Ban Appeal",
        style=nextcord.TextStyle.long,
        placeholder="Why should your ban be appealed? We recommend waiting 1-2 weeks before answering this question.",
        required=True,
        max_length=750,
    )

    media = nextcord.ui.TextInput(
        label = "Supporting Media",
        style=nextcord.TextStyle.long,
        placeholder='Feel free to send links to supporting media here.',
        required=False,
        max_length=150,
    )

    miscellaneous = nextcord.ui.TextInput(
        label="Anything else?",
        style=nextcord.TextStyle.long,
        placeholder='Is there anything else you would like us to know?',
        required=False,
        max_length=750,
    )

    async def on_submit(self, interaction: nextcord.Interaction):

        await interaction.response.send_message(f"Your appeal has been sent!", ephemeral=True)

        guild = self.bot.get_guild(self.bot.guild_id)
        appeal_channel = nextcord.utils.get(guild.channels, name="important-updates")
        appeal_embed = nextcord.Embed(title="Ban Appeal", color=light_orange)
        appeal_embed.add_field(name="User:", value=f"{interaction.user.name}#{interaction.user.discriminator}")
        appeal_embed.add_field(name="ID:", value=f"{interaction.user.id}", inline = False)
        appeal_embed.add_field(name="Appeal:", value=f"```\n{self.appeal.value}\n```", inline = False)
        if self.media.value:
            appeal_embed.add_field(name="Media Links:", value=f"{self.media.value}", inline = False)
        if self.miscellaneous.value:
            appeal_embed.add_field(name="Additional Information:", value=f"```\n{self.miscellaneous.value}\n```", inline = False)
        appeal_embed.timestamp = datetime.datetime.now()

        user_config = await self.bot.read_user_config(interaction.user.id)

        if "appeal_message_id" in user_config:
            appeal_message = await appeal_channel.fetch_message(user_config["appeal_message_id"])
            appeal_thread = nextcord.utils.get(appeal_message.channel.threads, name=f"{interaction.user.name}#{interaction.user.discriminator} ({interaction.user.id}) Ban Appeal")
            await appeal_thread.send("Appeal has been updated!", embed=appeal_embed)
        else:
            appeal_message = await appeal_channel.send(embed=appeal_embed)
            await appeal_message.add_reaction("🟢")
            await appeal_message.add_reaction("🟡")
            await appeal_message.add_reaction("🔴")
            await appeal_message.create_thread(name=f"{interaction.user.name}#{interaction.user.discriminator} ({interaction.user.id}) Ban Appeal")
            user_config["appeal_message_id"] = appeal_message.id

        user_config["check_appeal_date"] = datetime.datetime.now() + datetime.timedelta(days=14)
        await self.bot.update_user_config(interaction.user.id, user_config)

    async def on_error(self, interaction: nextcord.Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)


class BanAppealButton(nextcord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Appeal Ban', style=nextcord.ButtonStyle.blurple, custom_id="appeal")
    async def callback(self, interaction, button):
        """
        Confirm to appeal ban to bring up the modal.
        """

        await interaction.response.send_modal(BanAppeal(self.bot))

    async def on_timeout(self) -> None:
        self.callback.style = nextcord.ButtonStyle.grey
        self.callback.label = "Timed out!"
        self.callback.disabled = True

        await self.message.edit(view=self)


class ModerationCommands(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name="Delete Message",
            callback=self.delete
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='warn', description="Warn members of rule-breaking behavior.")
    async def warn(self, interaction: nextcord.Interaction, member: nextcord.Member, *, reason: str, attachment: nextcord.Attachment = None):
        """
        Warn members of rule-breaking behavior.
            - Generates an embed/message for the offender.
            - Generates an embed/message for response and mod-log.
            - Adds infraction to infraction history.
        """

        await interaction.response.defer()

        warn_message = nextcord.Embed(title='', color=yellow)
        warn_message.add_field(name='You have been warned!', value=f'Reason: {reason}', inline=False)
        warn_message.timestamp = datetime.datetime.now()

        warn_log = nextcord.Embed(title=f"{member.name}#{member.discriminator} has been warned.", color=yellow)
        warn_log.add_field(name=f"Reason: ", value=reason, inline=False)
        warn_log.add_field(name=f"User ID: ", value=f"{member.id} ({member.mention})", inline=False)
        warn_log.add_field(name=f"Responsible Moderator:", value=f"{interaction.user.name}#{interaction.user.discriminator} ({interaction.user.mention})", inline=False)
        warn_log.timestamp = datetime.datetime.now()

        warn_response = nextcord.Embed(title=f"", color=yellow)
        warn_response.add_field(name=f"Member warned!", value=f"{member.mention} has been warned.", inline=False)
        warn_response.add_field(name=f"Reason:", value=reason)
        warn_response.timestamp = datetime.datetime.now()

        if attachment:
            warn_message.set_image(url=attachment.proxy_url)
            warn_log.set_image(url=attachment.proxy_url)
            warn_response.set_image(url=attachment.proxy_url)

        try:
            await member.send(embed=warn_message)
        except Exception:
            warn_log.set_footer(text=f"Could not DM warn message.")

        await interaction.followup.send(embed=warn_response)
        guild = self.bot.get_guild(self.bot.guild_id)
        logs = nextcord.utils.get(guild.channels, name="logs")
        await logs.send(embed=warn_log)

        member_config = await self.bot.read_user_config(member.id)
        warning = {
            "type": "warn",
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name}#{interaction.user.discriminator})",
            "date": datetime.datetime.now()
        }

        if attachment:
            warning["attachment"] = attachment.proxy_url

        member_config["infractions"].append(warning)
        await self.bot.update_user_config(member.id, member_config)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='wm', description='Mute and add infraction points to a member.')
    async def wm(self, interaction: nextcord.Interaction, member: nextcord.Member, duration: str, *, reason: str, attachment: nextcord.Attachment = None):
        """
        Mute members for rule-breaking behavior.
            - Generates embed/message for the offender.
            - Generates an embed/message for response and mod-log.
            - Times out offender.
            - Adds infraction to infraction history.
            - Adds infraction points based on duration of mute.
            - Checks if infraction points exceed 30, and if so, notifies Chat Moderators.
        """

        await interaction.response.defer()

        seconds = await convert(duration)
        time_until = datetime.timedelta(seconds=seconds)
        time_until_dt = datetime.datetime.now() + time_until
        await member.timeout(time_until, reason=reason)

        member_config = await self.bot.read_user_config(member.id)
        if seconds >= 43200:
            member_config["infraction_points"] += 15
        elif seconds >= 21600:
            member_config["infraction_points"] += 10
        else:
            member_config["infraction_points"] += 5

        mute_message = nextcord.Embed(title='', color=orange)
        mute_message.add_field(name='You have been muted!',
                               value=f"""Reason: {reason}
                                         Duration: {duration}
                                         You will be unmuted {nextcord.utils.format_dt(time_until_dt, style='R')} at {nextcord.utils.format_dt(time_until_dt, style='t')}""",
                                inline=False)
        mute_message.add_field(name='Infraction Points:',
                               value=f'''You currently have `{member_config["infraction_points"]} infraction points`.
                                         Once you hit 30, you will be reviewed for a ban.''',
                               inline=False)
        mute_message.timestamp = datetime.datetime.now()

        mute_log = nextcord.Embed(title=f"{member.name}#{member.discriminator} has been muted.", color=orange)
        mute_log.add_field(name=f"Duration:", value=duration, inline=False)
        mute_log.add_field(name=f"Infraction points:", value=f"`{member_config['infraction_points']}`", inline=False)
        mute_log.add_field(name=f"Reason: ", value=reason, inline=False)
        mute_log.add_field(name=f"User ID:", value=f"{member.id} ({member.mention})", inline=False)
        mute_log.add_field(name=f"Responsible Moderator: ", value=f"{interaction.user.name}#{interaction.user.discriminator} ({interaction.user.mention})", inline=False)
        mute_log.timestamp = datetime.datetime.now()

        mute_response = nextcord.Embed(title=f"", color=orange)
        mute_response.add_field(name=f"Member muted!",
                                value=f"""{member.mention} will be unmuted {nextcord.utils.format_dt(time_until_dt, style='R')} at {nextcord.utils.format_dt(time_until_dt, style='t')}.
                                          They currently have `{member_config['infraction_points']} infraction points`.""",
                                inline=False)
        mute_response.add_field(name=f"Reason:", value=reason)
        mute_response.timestamp = datetime.datetime.now()

        if attachment:
            mute_message.set_image(url=attachment.proxy_url)
            mute_log.set_image(url=attachment.proxy_url)
            mute_response.set_image(url=attachment.proxy_url)

        try:
            await member.send(embed=mute_message)
        except Exception:
            mute_log.set_footer(text=f"Could not DM mute message.")

        await interaction.followup.send(embed=mute_response)
        guild = self.bot.get_guild(self.bot.guild_id)
        logs = nextcord.utils.get(guild.channels, name="logs")
        await logs.send(embed=mute_log)

        warning = {
            "type": "mute",
            "duration": duration,
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name}#{interaction.user.discriminator})",
            "date": datetime.datetime.now()
        }
        if attachment:
            warning["attachment"] = attachment.proxy_url
        member_config["infractions"].append(warning)
        await self.bot.update_user_config(member.id, member_config)

        if member_config["infraction_points"] >= 30:
            guild = self.bot.get_guild(self.bot.guild_id)
            update = nextcord.utils.get(guild.channels, name="important-updates")
            chat_mod = nextcord.utils.get(guild.roles, name='Chat Moderator')

            ban_warn_embed = nextcord.Embed(title='', color=red)
            ban_warn_embed.add_field(name='Member has reached 30 infraction points!',
                                     value=f'{member.mention} has {member_config["infraction_points"]} infraction points and should be reviewed for a ban.')

            await update.send(f"{chat_mod.mention}", embed=ban_warn_embed)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='mute', description='Mute members without adding infraction points.')
    async def mute(self, interaction: nextcord.Interaction, member: nextcord.Member, duration: str, *, reason: str, attachment: nextcord.Attachment = None):
        """
        Mutes members for any general reason.
            - Generates an embed/message for the offender.
            - Generates an embed/message for response and mod-log.
            - Times out offender.
            - NOT saved to infraction history.
        """

        await interaction.response.defer()

        seconds = await convert(duration)
        time_until = datetime.timedelta(seconds=seconds)
        time_until_dt = time_until + datetime.datetime.now()
        await member.timeout(time_until, reason=reason)

        mute_message = nextcord.Embed(title='', color=light_orange)
        mute_message.add_field(name='You have been muted!',
                               value=f"""Reason: {reason}
                                         Duration: {duration}
                                         You will be unmuted {nextcord.utils.format_dt(time_until_dt, style='R')} at {nextcord.utils.format_dt(time_until_dt, style='t')}""",
                                inline=False)
        mute_message.timestamp = datetime.datetime.now()

        mute_log = nextcord.Embed(title=f"{member.name}#{member.discriminator} has been muted.", color=light_orange)
        mute_log.add_field(name=f"Duration:", value=duration, inline=False)
        mute_log.add_field(name=f"Reason: ", value=reason, inline=False)
        mute_log.add_field(name=f"User ID:", value=f"{member.id} ({member.mention})", inline=False)
        mute_log.add_field(name=f"Responsible Moderator:", value=f"{interaction.user.name}#{interaction.user.discriminator} ({interaction.user.mention})", inline=False)
        mute_log.timestamp = datetime.datetime.now()

        mute_response = nextcord.Embed(title=f"", color=light_orange)
        mute_response.add_field(name=f"Member muted!",
                                value=f"{member.mention} will be unmuted {nextcord.utils.format_dt(time_until_dt, style='R')} at {nextcord.utils.format_dt(time_until_dt, style='t')}.",
                                inline=False)
        mute_response.add_field(name=f"Reason:", value=reason)
        mute_response.timestamp = datetime.datetime.now()

        if attachment:
            mute_message.set_image(url=attachment.proxy_url)
            mute_log.set_image(url=attachment.proxy_url)
            mute_response.set_image(url=attachment.proxy_url)

        try:
            await member.send(embed=mute_message)
        except Exception:
            mute_log.set_footer(text=f"Could not DM mute message.")

        await interaction.followup.send(embed=mute_response)
        guild = self.bot.get_guild(self.bot.guild_id)
        logs = nextcord.utils.get(guild.channels, name="logs")
        await logs.send(embed=mute_log)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name='unmute', description='Unmute members (idk what else to put here).')
    async def unmute(self, interaction: nextcord.Interaction, member: nextcord.Member, *, reason: str, attachment: nextcord.Attachment = None):

        """
        Unmute members for whatever reason.
            - Generates an embed/message for the user.
            - Generates an embed/message for response and mod-log.
            - Updates infraction history by editing the most recent infraction if it's a mute.
        """

        await interaction.response.defer()

        await member.timeout(None, reason=reason)

        unmute_message = nextcord.Embed(title='', color=green)
        unmute_message.add_field(name='You have been unmuted!',
                               value=f'Reason: {reason}',
                               inline=False)
        unmute_message.timestamp = datetime.datetime.now()

        unmute_log = nextcord.Embed(title=f"{member.name}#{member.discriminator} has been unmuted.", color=green)
        unmute_log.add_field(name=f"Reason: ", value=reason, inline=False)
        unmute_log.add_field(name=f"User ID:", value=f"{member.id} ({member.mention})", inline=False)
        unmute_log.add_field(name=f"Responsible Moderator: ", value=f"{interaction.user.name}#{interaction.user.discriminator} ({interaction.user.mention})", inline=False)
        unmute_log.timestamp = datetime.datetime.now()

        unmute_response = nextcord.Embed(title=f"", color=green)
        unmute_response.add_field(name=f"Member unmuted!", value=f"{member.mention} has been unmuted.", inline=False)
        unmute_response.add_field(name=f"Reason:", value=reason)
        unmute_response.timestamp = datetime.datetime.now()

        if attachment:
            unmute_message.set_image(url=attachment.proxy_url)
            unmute_log.set_image(url=attachment.proxy_url)
            unmute_response.set_image(url=attachment.proxy_url)

        try:
            await member.send(embed=unmute_message)
        except Exception:
            unmute_log.set_footer(text=f"Could not DM unmute message.")

        await interaction.followup.send(embed=unmute_response)
        guild = self.bot.get_guild(self.bot.guild_id)
        logs = nextcord.utils.get(guild.channels, name="logs")
        await logs.send(embed=unmute_log)

        member_config = await self.bot.read_user_config(member.id)

        try:
            # Checks if previous infraction is a mute, and if so, the infraction will be updated.
            if member_config['infractions'][-1]['type'] ==  "mute":
                member_config['infractions'][-1]["unmute reason"] = reason
                member_config['infractions'][-1]["unmute moderator"] = f"{interaction.user.mention} ({interaction.user.name}#{interaction.user.discriminator})"
                if attachment:
                    member_config['infractions'][-1]["unmute attachment"] = attachment.proxy_url
                await self.bot.update_user_config(member.id, member_config)
        except IndexError:
            pass

    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.command(name='kick', description="Kick members (pretend something is here...).")
    async def kick(self, interaction: nextcord.Interaction, member: nextcord.Member, *, reason: str, attachment: nextcord.Attachment = None):

        """
        Kick members for whatever reason.
            - Generates an embed/messsage for the offender.
            - Generates an embed/message for response and mod-log.
            - Adds infraction to infraction history.
        """

        await interaction.response.defer()

        kick_message = nextcord.Embed(title='', color=dark_orange)
        kick_message.add_field(name='You have been kicked!', value=f'Reason: {reason}', inline=False)
        kick_message.timestamp = datetime.datetime.now()

        kick_log = nextcord.Embed(title=f"{member.name}#{member.discriminator} has been kicked.", color=dark_orange)
        kick_log.add_field(name=f"Reason: ", value=reason, inline=False)
        kick_log.add_field(name=f"User ID: ", value=f"{member.id} ({member.mention})", inline=False)
        kick_log.add_field(name=f"Responsible Moderator: ", value=f"{interaction.user.name}#{interaction.user.discriminator} ({interaction.user.mention})", inline=False)
        kick_log.timestamp = datetime.datetime.now()

        kick_response = nextcord.Embed(title=f"", color=dark_orange)
        kick_response.add_field(name=f"Member kicked!", value=f"{member.mention} has been kicked.", inline=False)
        kick_response.add_field(name=f"Reason:", value=reason)
        kick_response.timestamp = datetime.datetime.now()

        if attachment:
            kick_message.set_image(url=attachment.proxy_url)
            kick_log.set_image(url=attachment.proxy_url)
            kick_response.set_image(url=attachment.proxy_url)

        try:
            await member.send(embed=kick_message)
        except Exception:
            kick_log.set_footer(text=f"Could not DM kick message.")

        # Kick the member AFTER the message is sent.
        await interaction.guild.kick(member, reason=reason)

        await interaction.followup.send(embed=kick_response)
        guild = self.bot.get_guild(self.bot.guild_id)
        logs = nextcord.utils.get(guild.channels, name="logs")
        await logs.send(embed=kick_log)

        member_config = await self.bot.read_user_config(member.id)
        warning = {
            "type": "kick",
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name}#{interaction.user.discriminator})",
            "date": datetime.datetime.now()
        }
        if attachment:
            warning["attachment"] = attachment.proxy_url
        member_config["infractions"].append(warning)
        await self.bot.update_user_config(member.id, member_config)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.command(name='ban', description="Ban members due to rule-breaking behavior.")
    async def ban(self, interaction: nextcord.Interaction, member: nextcord.Member, *, reason: str, attachment: nextcord.Attachment = None):

        """
        Ban a member for rule-breaking behavior or when 30 infraction points are reached.
            - Generates an embed/message for offender.
            - Generates an embed/message for response and mod-log.
            - Adds infraction to infraction history.
        """

        await interaction.response.defer()

        ban_message = nextcord.Embed(title='', color=red)
        ban_message.add_field(name='You have been banned!',
                              value=f'Reason: {reason}',
                              inline=False)
        ban_message.add_field(name='Appeal',
                              value='If you wish to appeal your ban, you may do so by joining the following server: https://nextcord.gg/RHx7deYQ3q')
        ban_message.timestamp = datetime.datetime.now()

        ban_log = nextcord.Embed(title=f"{member.name}#{member.discriminator} has been banned.", color=red)
        ban_log.add_field(name=f"Reason: ", value=reason, inline=False)
        ban_log.add_field(name=f"User ID: ", value=f"{member.id} ({member.mention})", inline=False)
        ban_log.add_field(name=f"Responsible Moderator: ", value=f"{interaction.user.name}#{interaction.user.discriminator} ({interaction.user.mention})", inline=False)
        ban_log.timestamp = datetime.datetime.now()

        ban_response = nextcord.Embed(title=f"", color=red)
        ban_response.add_field(name=f"Member banned!", value=f"{member.mention} has been banned.", inline=False)
        ban_response.add_field(name=f"Reason:", value=reason)
        ban_response.timestamp = datetime.datetime.now()

        if attachment:
            ban_message.set_image(url=attachment.proxy_url)
            ban_log.set_image(url=attachment.proxy_url)
            ban_response.set_image(url=attachment.proxy_url)

        try:
            await member.send(embed=ban_message)
        except Exception:
            ban_log.set_footer(text=f"Could not DM ban message.")
        # Ban AFTER message is sent.
        await interaction.guild.ban(member, reason=reason)

        await interaction.followup.send(embed=ban_response)
        guild = self.bot.get_guild(self.bot.guild_id)
        logs = nextcord.utils.get(guild.channels, name="logs")
        await logs.send(embed=ban_log)

        member_config = await self.bot.read_user_config(member.id)
        warning = {
            "type": "ban",
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name}#{interaction.user.discriminator})",
            "date": datetime.datetime.now()
        }
        if attachment:
            warning["attachment"] = attachment.proxy_url
        member_config["infractions"].append(warning)
        await self.bot.update_user_config(member.id, member_config)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.command(name='forceban', description="Force-ban users not present in the server.")
    async def forceban(self, interaction: nextcord.Interaction, user_id: str, *, reason: str, attachment: nextcord.Attachment = None):

        """
        Froe-ban a user (not member) for rule-breaking behavior.
            - Force-create an object from user id.
            - Generates an embed/message for response and mod-log.
            - Adds infraction to infraction history.
        """

        await interaction.response.defer()

        try:
            member_id = int(member_id)
        except:
            raise app_commands.AppCommandError("Please enter an integer for `member_id`.")
        await interaction.guild.ban(nextcord.Object(member_id), reason=reason)

        ban_log = nextcord.Embed(title=f"{member_id} has been force-banned.", color=red)
        ban_log.add_field(name=f"Reason: ", value=reason, inline=False)
        ban_log.add_field(name=f"Responsible Moderator: ",
                          value=f"{interaction.user.name}#{interaction.user.discriminator}"
                                f" ({interaction.user.mention})", inline=False)
        ban_log.timestamp = datetime.datetime.now()

        ban_response = nextcord.Embed(title=f"", color=red)
        ban_response.add_field(name=f"Member force-banned!", value=f"{member_id} has been force-banned.",
                                inline=False)
        ban_response.add_field(name=f"Reason:", value=reason)
        ban_response.timestamp = datetime.datetime.now()

        if attachment:
            ban_log.set_image(url=attachment.proxy_url)
            ban_response.set_image(url=attachment.proxy_url)

        await interaction.followup.send(embed=ban_response)
        guild = self.bot.get_guild(self.bot.guild_id)
        logs = nextcord.utils.get(guild.channels, name="logs")
        await logs.send(embed=ban_log)

        member_config = await self.bot.read_user_config(member_id)
        warning = {
            "type": "force-ban",
            "reason": reason,
            "moderator": f"{interaction.user.mention} ({interaction.user.name}#{interaction.user.discriminator})",
            "date": datetime.datetime.now()
        }
        if attachment:
            warning["attachment"] = attachment.proxy_url
        member_config["infractions"].append(warning)
        await self.bot.update_user_config(member_id, member_config)

    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete(self, interaction:nextcord.Interaction, message: nextcord.Message):

        """
        Deletes a message using the bot.
        """

        await interaction.response.defer(ephemeral=True)
        await message.delete()

        message_log = nextcord.Embed(title=f"", color=yellow)
        message_log.add_field(name=f"Responsible Moderator: ",
                              value=f"{interaction.user.name}#{interaction.user.discriminator}",
                              inline=False)
        message_log.add_field(name="Message Content: ", value=f"```{message.content}```", inline=False)
        message_log.set_author(name=f"{message.author.name}#{message.author.discriminator}'s message was deleted.",
                               url=f"{message.author.avatar.url}")
        message_log.timestamp = datetime.datetime.now()

        if message.attachments:
            message_log.set_image(url=message.attachments[0].proxy_url)

        guild = self.bot.get_guild(self.bot.guild_id)
        logs = nextcord.utils.get(guild.channels, name="logs")

        await logs.send(embed=message_log)

        if len(message.attachments) > 1:

            attachments_count = 1

            for attachment in message.attachments:

                attachment_embed = nextcord.Embed(title="", color=nextcord.Color.blue)

                try:
                    attachment_embed.set_image(url=message.attachments[attachments_count].proxy_url)
                    attachment_embed.set_footer(text=f"{attachments_count + 1}/{len(message.attachments)} attachments")
                except IndexError:
                    break

                attachments_count += 1
                await logs.send(embed=attachment_embed)

        await interaction.followup.send("`Message successfully deleted!`", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCommands(bot), guilds=[nextcord.Object(id=bot.guild_id)])
    bot.add_view(BanAppealButton(bot))