import time
from datetime import datetime

from nextcord import Activity, ActivityType, Intents

from bot_base import APBot
from database_handler import Database


DEFAULT_COLORS = {
    "yellow": 0xFFFF00,
    "orange": 0xFFA500,
    "light_orange": 0xFFA07A,
    "dark_orange": 0xFF5733,
    "red": 0xFF0000,
    "green": 0x00FF00,
    "blue": 0x00FFFF,
}


def build_default_colors(conf) -> dict:
    colors = DEFAULT_COLORS.copy()
    configured_colors = conf.get("colors", {})
    colors.update(
        {
            name: int(value, 16) if isinstance(value, str) else int(value)
            for name, value in configured_colors.items()
        }
    )
    return colors


def register_ready_event(bot: APBot) -> None:
    @bot.event
    async def on_ready() -> None:
        print(
            f"Logged in as {bot.user} at "
            f"{datetime.fromtimestamp(time.time()).strftime(r'%d-%b-%y, %H:%M:%S')}"
        )


def build_bot(conf) -> APBot:
    intents = Intents.default()
    intents.members = True
    intents.message_content = True

    bot: APBot = APBot(
        command_prefix=conf.get("command_prefix", "ap:"),
        strip_after_prefix=True,
        intents=intents,
        activity=Activity(type=ActivityType.playing, name="DM me to contact mods!"),
    )

    register_ready_event(bot)
    bot.colors = build_default_colors(conf)
    bot.config = conf
    bot.db = Database(conf)
    return bot
