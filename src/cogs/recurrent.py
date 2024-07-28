"""from nextcord.ext import commands
from bot_base import APBot
from nextcord import Message, Embed
from collections import defaultdict
import random

class Recurrent(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot
        self.message_count_cache = defaultdict(int)

    @commands.Cog.listener("on_message")
    async def _recurrent_on_message(self, message: Message) -> None:
        conf = self.bot.config.get("recurrent_config")

        if message.channel.id not in [int(i) for i in conf.keys()]:
            return

        channel_config = conf[str(message.channel.id)]
        self.message_count_cache[message.channel.id] += 1

        if self.message_count_cache[message.channel.id] < channel_config["limit"]:
            return

        self.message_count_cache[message.channel.id] = 0

        await message.channel.send(embed=Embed.from_dict(random.choice(channel_config["dicts"])))


def setup(bot: APBot):
    bot.add_cog(Recurrent(bot))
""" 
from nextcord.ext import commands, tasks
from bot_base import APBot
from nextcord import Embed, Interaction, SlashOption, slash_command, Message
from collections import defaultdict
import random
import time

class Recurrent(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot
        self.message_count_cache = defaultdict(int)
        self.send_recurrent_message.start()  

    @tasks.loop(minutes=1)
    async def send_recurrent_message(self):
        current_time = time.time()
        try:
            channels = await self.bot.db.recurrent.get_all_channels()
            for channel_id in channels:
                try:
                    next_message_time = await self.bot.db.recurrent.get_next_message_time(channel_id)
                    if current_time >= next_message_time:
                        random_message = await self.bot.db.recurrent.get_random_message(channel_id)
                        if random_message:
                            channel = self.bot.get_channel(channel_id)
                            if channel:
                                await channel.send(embed=Embed(description=random_message))
                            await self.bot.db.recurrent.update_next_message_time(channel_id, current_time + 60)
                        else:
                            print(f"No random message available for channel_id {channel_id}")
                except Exception as e:
                    print(f"Error sending recurrent message to channel {channel_id}: {e}")
        except Exception as e:
            print(f"Error retrieving channels: {e}")

    @slash_command(name="recurrent", description="Manage recurring messages")
    async def _recurrent(self, inter: Interaction):
        await inter.response.send_message("Subcommands: /recurrent add, /recurrent clear, /recurrent list, /recurrent remove", ephemeral=True)

    @_recurrent.subcommand(name="add", description="Add a recurring message to a channel")
    async def add(self, inter: Interaction, channel_id: str = SlashOption(description="ID of the channel where the message will be sent", required=True), message: str = SlashOption(description="Message to send", required=True)):
        try:
            await inter.response.defer(ephemeral=True)
            channel_id = int(channel_id)
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await inter.followup.send(f"Channel ID {channel_id} not found.", ephemeral=True)
                return
            await self.bot.db.recurrent.add_message(channel_id, message)
            await inter.followup.send(f"Recurring message added to channel {channel_id}")
        except ValueError:
            await inter.followup.send("Invalid channel ID provided.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error adding recurring message: {e}", ephemeral=True)

    @_recurrent.subcommand(name="clear", description="Clear all recurring messages")
    async def clear(self, inter: Interaction):
        try:
            await inter.response.defer(ephemeral=True)
            await self.bot.db.recurrent.clear_all_data()
            await inter.followup.send("All recurring messages have been cleared.")
        except Exception as e:
            await inter.followup.send(f"Error clearing recurring messages: {e}", ephemeral=True)

    @_recurrent.subcommand(name="list", description="List all recurring messages in a channel")
    async def list(self, inter: Interaction, channel_id: str = SlashOption(description="ID of the channel to list messages from", required=True)):
        try:
            await inter.response.defer(ephemeral=True)
            channel_id = int(channel_id)
            messages = await self.bot.db.recurrent.get_messages(channel_id)
            if not messages:
                await inter.followup.send(f"No recurring messages found for channel {channel_id}.", ephemeral=True)
                return
            message_list = "\n".join([f"{idx + 1}: {msg}" for idx, msg in enumerate(messages)])
            await inter.followup.send(f"Recurring messages for channel {channel_id}:\n{message_list}", ephemeral=True)
        except ValueError:
            await inter.followup.send("Invalid channel ID provided.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error listing recurring messages: {e}", ephemeral=True)

    @_recurrent.subcommand(name="remove", description="Remove a recurring message by index")
    async def remove(self, inter: Interaction, channel_id: str = SlashOption(description="ID of the channel to remove the message from", required=True), index: int = SlashOption(description="Index of the message to remove", required=True)):
        try:
            await inter.response.defer(ephemeral=True)
            channel_id = int(channel_id)
            messages = await self.bot.db.recurrent.get_messages(channel_id)
            if not (0 < index <= len(messages)):
                await inter.followup.send(f"Invalid index provided. Please provide a number between 1 and {len(messages)}.", ephemeral=True)
                return
            await self.bot.db.recurrent.remove_message(channel_id, index - 1)
            await inter.followup.send(f"Removed message {index} from channel {channel_id}.", ephemeral=True)
        except ValueError:
            await inter.followup.send("Invalid channel ID or index provided.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error removing recurring message: {e}", ephemeral=True)

    @commands.Cog.listener("on_message")
    async def _recurrent_on_message(self, message: Message) -> None:
        conf = self.bot.config.get("recurrent_config")
        if not conf or message.channel.id not in [int(i) for i in conf.keys()]:
            return
        channel_config = conf.get(str(message.channel.id))
        if not channel_config:
            return
        self.message_count_cache[message.channel.id] += 1
        if self.message_count_cache[message.channel.id] < channel_config.get("limit", 0):
            return
        self.message_count_cache[message.channel.id] = 0
        embed = Embed(description=random.choice(channel_config.get("dicts", [])))
        await message.channel.send(embed=embed)

def setup(bot):
    bot.add_cog(Recurrent(bot))











