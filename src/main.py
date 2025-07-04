import os
from dotenv import load_dotenv
import time
from datetime import datetime
from typing import List
from nextcord import Guild, Activity, ActivityType, Intents
from bot_base import APBot
from config_handler import Config
from database_handler import Database
import logging
load_dotenv()
print("Current working directory:", os.getcwd())

config_path = "config.json"
if not os.path.exists(config_path):
    raise FileNotFoundError(f"Config file not found: {config_path}")
if os.path.getsize(config_path) == 0:
    raise ValueError(f"Config file is empty: {config_path}")

# logging.basicConfig(level=logging.DEBUG)

conf = Config(config_path)

bot: APBot = APBot(
    command_prefix=conf.get("command_prefix", "ap:"),
    strip_after_prefix=True,
    intents=Intents.all(),
    activity=Activity(type=ActivityType.playing, name="DM me to contact mods!"),
    default_guild_ids=[conf.get("guild_id")],
)

cogs: List[str] = [
    # "cogs.moderation.commands",  
    # "cogs.moderation.infraction",
    "cogs.bonk",  
   # "cogs.recurrent", 
 #   "cogs.tags",
   # "cogs.study",
    "cogs.errorhandler",
   # "cogs.events",
    "cogs.modmail",
    "cogs.special",  # Special permissions for emotional support
    
]

@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} at {datetime.fromtimestamp(time.time()).strftime(r'%d-%b-%y, %H:%M:%S')}")

async def startup(conf: Config):
    bot.rolemenu_view_set = False
    for extension in cogs:
        try:
            bot.load_extension(extension)
            print(f"Successfully loaded extension {extension}")
        except Exception as e:
            print(f"Failed to load extension {extension}\n{type(e).__name__}: {e}")

    await bot.wait_until_ready()

    try:
        bot.guild = await bot.fetch_guild(conf.get("guild_id"))
        print(f"Fetched guild {bot.guild.name}")
    except Exception as e:
        print(f"Failed to fetch guild\n{type(e).__name__}: {e}")

    bot.db.bot_user_id = bot.user.id

    try:
        await bot.resync_slash_commands()  # Ensure this is called
        print("Commands resynced successfully.")
    except Exception as e:
        print(f"Failed to resync commands\n{type(e).__name__}: {e}")

    bot.owner_ids = bot.config.get("owner_ids", [])

    print("All Ready")

default_colors = {
    "yellow": 0xFFFF00,
    "orange": 0xFFA500,
    "light_orange": 0xFFA07A,
    "dark_orange": 0xFF5733,
    "red": 0xFF0000,
    "green": 0x00FF00,
    "blue": 0x00FFFF,
}

default_colors.update({i: int(j, 16) for i, j in conf.get("colors", {}).items()})
bot.colors = default_colors

bot.config = conf
bot.db = Database(conf)

bot.loop.create_task(startup(bot.config))
bot.run(os.getenv("APBOT_BOT_TOKEN"))