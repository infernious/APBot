from nextcord.ext import commands
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
        chosen_one = random.choice(channel_config["dicts"])
        await message.channel.send(embed=Embed.from_dict(chosen_one))
        self.message_count_cache[message.channel.id] = 0
