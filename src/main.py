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
)

cogs: List[str] = [
     "cogs.logs", 
     "cogs.moderation.commands",  
     "cogs.moderation.infraction",
     "cogs.bonk",  
     "cogs.recurrent", 
     "cogs.tags",
     "cogs.study",
     "cogs.events",
     "cogs.modmail",
     "cogs.special",  
     "cogs.moderation.appeal",
     "cogs.moderation.errorhandler",
     "cogs.moderation.decay",
     "cogs.rolereact",
     "cogs.boostrolemanager",
     "cogs.role_log",
     "cogs.voice_log",
]

@bot.event
async def on_ready() -> None:
    print(f"Logged in as {bot.user} at {datetime.fromtimestamp(time.time()).strftime(r'%d-%b-%y, %H:%M:%S')}")

    #await bot.db.emergency.emergency.delete_many({})
   #  print("✅ Emergency cooldowns cleared")

async def startup(conf: Config):
    bot.rolemenu_view_set = False

    # Load all extensions
    for extension in cogs:
        try:
            bot.load_extension(extension)
            print(f"Successfully loaded extension {extension}")
        except Exception as e:
            print(f"Failed to load extension {extension}\n{type(e).__name__}: {e}")

    await bot.wait_until_ready()

    # Fetch guild
    try:
        bot.guild = await bot.fetch_guild(conf.get("guild_id"))
        print(f"Fetched guild {bot.guild.name}")
    except Exception as e:
        print(f"Failed to fetch guild\n{type(e).__name__}: {e}")

    bot.db.bot_user_id = bot.user.id

    # ✅ Sync only for this guild
    try:
        guild_id = conf.get("guild_id")
        await bot.sync_application_commands(guild_id=guild_id)
        print(f"Guild commands synced to {conf.get('guild_id')}")
    except Exception as e:
        print(f"Failed to sync commands\n{type(e).__name__}: {e}")

    bot.owner_ids = bot.config.get("owner_ids", [])
    print("All Ready")

# Define colors
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
