import os

import motor.motor_asyncio as motor

from bot_base import APBot

db_client = motor.AsyncIOMotorClient(os.environ.get("DATABASE_PASSWORD"))
db = db_client["ap-students"]

bot = APBot(db)

bot.run(os.environ.get("DISCORD_BOT_SECRET"))
