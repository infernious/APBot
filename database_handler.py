import motor.motor_asyncio as motor
from config_handler import Config

class Database:
    def __init__(self, conf: Config):
        self.database_client = motor.AsyncIOMotorClient(conf.get("mongo_connect_url"))
        self.database = self.database_client["ap-students"]

        self.conf = conf

    async def read_user_config(self, user_id: int):
        config_from_db = await self.database["user_config"].find_one({"user_id": user_id})

        if config_from_db is None:
            config_from_db = {"user_id": user_id, "infraction_points": 0, "infractions": []}
            await self.database["user_config"].insert_one(config_from_db)

        return config_from_db

    async def update_user_config(self, user_id: int, new_config):
        old_config = await self.database["user_config"].find_one({"user_id": user_id})

        if old_config is None:
            config = {"user_id": user_id, "infraction_points": 0, "infractions": []}
            old_config = await self.database["user_config"].insert_one(config)

        _id = old_config["_id"]
        await self.database["user_config"].replace_one({"_id": _id}, new_config)
