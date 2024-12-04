import os
import json
import motor.motor_asyncio as motor

import discord
from discord.ext import commands

database_password = os.environ.get("DATABASE_PASSWORD")
db_client = motor.AsyncIOMotorClient(database_password)
db = db_client["ap-students"]

config_file = open('config.json')
config = json.load(config_file)


class APBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix=config["command_prefix"],
            intents=discord.Intents.all(),
            application_id=config["application_id"],
        )

    async def setup_hook(self) -> None:
        initial_extensions = ['cogs.errorhandler',
                              'cogs.events',
                              'cogs.meta',
                              'cogs.moderation.appeal',
                              'cogs.moderation.commands',
                              'cogs.moderation.decay',
                              'cogs.modmail',
                              'cogs.rolereact',
                              'cogs.study',
                              # 'cogs.threads',
                              ]
        for extension in initial_extensions:
            await self.load_extension(extension)
        await bot.tree.sync(guild=discord.Object(id=config["guild_id"]))

    async def on_ready(self):
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="DM me to contact mods!"))
        print(f'Joined: {bot.user}')

    async def read_user_config(self, user_id: int):

        config_from_db = await db["user_config"].find_one({"user_id": user_id})

        if config_from_db is None:
            config_from_db = {
                "user_id": user_id,
                "infraction_points": 0,
                "infractions": []
            }
            await db["user_config"].insert_one(config_from_db)

        return config_from_db

    async def update_user_config(self, user_id: int, new_config):

        old_config = await db["user_config"].find_one({"user_id": user_id})

        if old_config is None:
            config = {
                "user_id": user_id,
                "infraction_points": 0,
                "infractions": []
            }
            old_config = await db["user_config"].insert_one(config)

        _id = old_config['_id']
        await db["user_config"].replace_one({"_id": _id}, new_config)


bot = APBot()
bot.guild_id = config["guild_id"]
bot.user_config = db["user_config"]

token = os.environ.get("DISCORD_BOT_SECRET")
bot.run(token)