import nextcord
from nextcord.ext import commands
import json
import traceback
from bot_base import APBot


class RawReactionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("config.json", "r") as f:
            config = json.load(f)

        self.reaction_logs_channel_id = config.get("reaction_logs_channel")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: nextcord.RawReactionActionEvent):
        try:            
            if payload.user_id == self.bot.user.id:
                return
            
            channel = self.bot.get_channel(payload.channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(payload.channel_id)
            
            message = await channel.fetch_message(payload.message_id)
            emoji = ""
            if payload.emoji.id:
                emoji = "<:" + payload.emoji.name + ":" + str(payload.emoji.id) + ">" 
            else:
                emoji = payload.emoji
            user = self.bot.get_user(payload.user_id) or await self.bot.fetch_user(payload.user_id)
      
            logs_channel = self.bot.get_channel(self.reaction_logs_channel_id)
            if logs_channel:
                embed = nextcord.Embed(
                    description=f"**{user.mention} reacted {emoji} in {channel.mention}** [Jump to Message]({message.jump_url})",
                    color=nextcord.Color.green()
                )
                embed.set_author(name=user.name, icon_url=user.avatar.url)
                embed.add_field(name="Message Content", value=message.content[:1900], inline=False)
                embed.set_footer(text=f"Reactor ID: {payload.user_id} • {payload.emoji.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                try:
                    await logs_channel.send(embed=embed)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error in on_raw_reaction_add: {type(e).__name__}: {e}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: nextcord.RawReactionActionEvent):
        try:            
            if payload.user_id == self.bot.user.id:
                return
            
            channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            emoji = ""
            if payload.emoji.id:
                emoji = "<:" + payload.emoji.name + ":" + str(payload.emoji.id) + ">" 
            else:
                emoji = payload.emoji
            user = self.bot.get_user(payload.user_id) or await self.bot.fetch_user(payload.user_id)

            logs_channel = self.bot.get_channel(self.reaction_logs_channel_id)
            if logs_channel:
                embed = nextcord.Embed(
                    description=f"**{user.mention} removed {emoji} in {channel.mention}** [Jump to Message]({message.jump_url})",
                    color=nextcord.Color.red()
                )
                embed.set_author(name=user.name, icon_url=user.avatar.url)
                embed.add_field(name="Message Content", value=message.content[:1900], inline=False)
                embed.set_footer(text=f"Reactor ID: {payload.user_id} • {payload.emoji.id} • {nextcord.utils.utcnow().strftime('%Y-%m-%d %I:%M %p UTC')}")
                try:
                    await logs_channel.send(embed=embed)
                except Exception:
                    pass            
        except Exception as e:
            print(f"Error in on_raw_reaction_remove: {type(e).__name__}: {e}")
            traceback.print_exc()

def setup(bot: APBot):
    bot.add_cog(RawReactionCog(bot))