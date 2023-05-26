import os
import json
import motor.motor_asyncio as motor
from bot_base import APBot

db_client = motor.AsyncIOMotorClient(os.environ.get("DATABASE_PASSWORD"))
db = db_client["ap-students"]

bot = APBot(db)

# bot.run(os.environ.get("DISCORD_BOT_SECRET"))
bot.run("MTA5OTQzODYwMzAzOTQyODY4OA.GBQE5d.kBtFLtbAQxJ2ynBUmF6FOLmstVopWQmAfec_tA")
