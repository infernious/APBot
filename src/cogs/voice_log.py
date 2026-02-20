import nextcord
from nextcord.ext import commands
from bot_base import APBot
import json


class VoiceLogCog(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot
        
        with open("config.json", "r") as f:
            config = json.load(f)
        
        self.voice_logs_channel_id = config.get("voice_logs_channel")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: nextcord.Member, before: nextcord.VoiceState, after: nextcord.VoiceState):
        try:
            logs_channel = self.bot.get_channel(self.voice_logs_channel_id)
            if not logs_channel:
                return

            # VC Join
            if before.channel is None and after.channel is not None:
                embed = nextcord.Embed(
                    description=f"{member.mention} joined **{after.channel.mention}**",
                    color=nextcord.Color.green()
                )
                embed.set_author(name=member.name, icon_url=member.avatar.url)
                embed.set_footer(text=f"Member ID: {member.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                await logs_channel.send(embed=embed)

            # VC Leave
            elif before.channel is not None and after.channel is None:
                embed = nextcord.Embed(
                    description=f"{member.mention} left **{before.channel.mention}**",
                    color=nextcord.Color.red()
                )
                embed.set_author(name=member.name, icon_url=member.avatar.url)
                embed.set_footer(text=f"Member ID: {member.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                await logs_channel.send(embed=embed)

            # VC Move (unknown if user moved themselves)
            elif before.channel != after.channel and before.channel is not None and after.channel is not None:
                moved_by = "Unknown"
                try:
                    async for entry in member.guild.audit_logs(limit=5, action=nextcord.AuditLogAction.member_move):
                        if entry.target.id == member.id:
                            moved_by = entry.user.mention
                            break
                except Exception:
                    pass
                
                embed = nextcord.Embed(
                    description=f"{member.mention} was moved from **{before.channel.mention}** to **{after.channel.mention}**  by: {moved_by}",
                    color=nextcord.Color.blue()
                )
                embed.set_author(name=member.name, icon_url=member.avatar.url)
                embed.set_footer(text=f"Member ID: {member.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                await logs_channel.send(embed=embed)

            # Server mute
            if before.mute is False and after.mute is True:
                muted_by = "Unknown"
                try:
                    async for entry in member.guild.audit_logs(limit=5, action=nextcord.AuditLogAction.member_update):
                        if entry.target.id == member.id and entry.changes.after.mute is True:
                            muted_by = entry.user.mention
                            break
                except Exception:
                    pass
                
                embed = nextcord.Embed(
                    description=f"{member.mention} was server muted in **{after.channel.mention}** by {muted_by}",
                    color=nextcord.Color.orange()
                )
                embed.set_author(name=member.name, icon_url=member.avatar.url)
                embed.set_footer(text=f"Member ID: {member.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                await logs_channel.send(embed=embed)

            # Server unmute
            if before.mute is True and after.mute is False:
                unmuted_by = "Unknown"
                try:
                    async for entry in member.guild.audit_logs(limit=5, action=nextcord.AuditLogAction.member_update):
                        if entry.target.id == member.id and entry.changes.after.mute is False:
                            unmuted_by = entry.user.mention
                            break
                except Exception:
                    pass
                
                embed = nextcord.Embed(
                    description=f"{member.mention} was server unmuted in **{after.channel.mention}** by {unmuted_by}",
                    color=nextcord.Color.gold()
                )
                embed.set_author(name=member.name, icon_url=member.avatar.url)
                embed.set_footer(text=f"Member ID: {member.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                await logs_channel.send(embed=embed)
            # Server deafen
            if before.deaf is False and after.deaf is True:
                deafened_by = "Unknown"
                try:
                    async for entry in member.guild.audit_logs(limit=5, action=nextcord.AuditLogAction.member_update):
                        if entry.target.id == member.id and entry.changes.after.deaf is True:
                            deafened_by = entry.user.mention
                            break
                except Exception:
                    pass
                
                embed = nextcord.Embed(
                    description=f"{member.mention} was server deafened in **{after.channel.mention}** by {deafened_by}",
                    color=nextcord.Color.orange()
                )
                embed.set_author(name=member.name, icon_url=member.avatar.url)
                embed.set_footer(text=f"Member ID: {member.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                await logs_channel.send(embed=embed)
            # Server undeafen
            if before.deaf is True and after.deaf is False:
                undeafened_by = "Unknown"
                try:
                    async for entry in member.guild.audit_logs(limit=5, action=nextcord.AuditLogAction.member_update):
                        if entry.target.id == member.id and entry.changes.after.deaf is False:
                            undeafened_by = entry.user.mention
                            break
                except Exception:
                    pass
                
                embed = nextcord.Embed(
                    description=f"{member.mention} was server undeafened in **{after.channel.mention}** by {undeafened_by}",
                    color=nextcord.Color.gold()
                )
                embed.set_author(name=member.name, icon_url=member.avatar.url)
                embed.set_footer(text=f"Member ID: {member.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                await logs_channel.send(embed=embed)

        except Exception as e:
            print(f"Error in on_voice_state_update: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()


def setup(bot: APBot):
    bot.add_cog(VoiceLogCog(bot))