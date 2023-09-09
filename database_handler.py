import motor.motor_asyncio as motor
from config_handler import Config
from datetime import datetime

class Database:
    def __init__(self, conf: Config):
        self.database_client = motor.AsyncIOMotorClient(conf.get("mongo_connect_url"))
        self.database = self.database_client["ap-students"]

        self.conf = conf

    async def set_user_study_expiry(self, user_id, study_expires_at):
        # add a user to the database with study expires_at epoch timestamp
        ...

    async def get_user_study_expiry(self, user_id) -> int:
        # return the epoch timestamp when the user's study role should be removed at
        ...

    async def get_all_study_students(self) -> dict[int, int]:
        # return a dict of users with study role like so:
        # {
        #     "USER_ID: int": "STUDY_EXPIRES_AT: int",
        #     "USER_ID: int": "STUDY_EXPIRES_AT: int",
        #     "USER_ID: int": "STUDY_EXPIRES_AT: int"
        # }
        ...

    async def set_reminder(self, user_id: int, expires_at: int, message: str):
        # Add a reminder
        ...

    async def remove_bonk(self, user_id: int, expires_at: int, message: str):
        # Remove reminder for user_id which has given params
        ...

    async def remove_all_bonks(self, user_id: int):
        # remove all bonks for user with user_id
        ...

    async def get_all_user_reminders(self, user_id: int):
        # return a list of reminders like soo:
        # [
        #     [
        #         "EXPIRES_AT: int",
        #         "MESSAGE: str"
        #     ],
        #     [
        #         "EXPIRES_AT: int",
        #         "MESSAGE: str"
        #     ]
        # ]
        ...

    async def get_all_reminders(self):
        # Return all reminders known to the bot in this format:
        # [
        #         [
        #             "USER_ID: INT",
        #             "EXPIRES_AT: int",
        #             "MESSAGE: str"
        #         ],
        #         [
        #             "USER_ID: INT",
        #             "EXPIRES_AT: int",
        #             "MESSAGE: str"
        #         ]
        # ]
        ...

    async def get_decay_date(self) -> datetime:
        # return datetime object
        ...
    
    async def remove_one_inf(self) -> datetime:
        # return next decay date datetime obj. Return `false` if function failed
        # I believe it is something like this:
        # await self.bot.user_config.update_many({'infraction_points': {'$gt': 0}}, {'$inc': {'infraction_points': -1}})
        #
        # Also, set decay_date to +7 days.
        ...

    async def get_appeals(self) -> list[dict[str, str]]:
        # Return all appeal messages that should be processed, like so:
        # {
        #     "USER_ID: int": "MESSAGE_ID: int",
        #     "USER_ID: int": "MESSAGE_ID: int",
        #     "USER_ID: int": "MESSAGE_ID: int"
        # }
        ...
    
    async def remove_pending_appeal(self, user_id):
        ...

    async def get_user_infractions(self, user_id):
        ...

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
