import json
import os
from datetime import datetime
from typing import List, Optional, Union

import motor.motor_asyncio as motor

from config_handler import Config


class Database:
    def __init__(self, conf: Config):
        self.bot_user_id: int
        self.database_client = motor.AsyncIOMotorClient(os.environ.get("DATABASE_PASSWORD"))
        self.database = self.database_client["ap-students"]
        self.user_config = self.database["user_config"]
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

    async def set_user_study_end(self, user_id: int, study_expires_at: int):
        """Set the time at which study will expire for a particular user"""
        user_config = await self.read_user_config(user_id)
        user_config["study_expires_at"] = study_expires_at
        await self.update_user_config(user_id, user_config)

    async def get_user_study_end(self, user_id: int) -> Optional[int]:
        """Get the time at which study expires for a particular user"""
        user_config = await self.read_user_config(user_id)
        if "study_expires_at" in user_config:
            return user_config["study_expires_at"]
        else:
            return None

    async def get_all_study_students(self) -> dict[int, int]:
        """Return all users with the study role"""
        cursor = self.user_config.find({"study_expires_at": {"$exists": True}})
        all_study_students = {}
        for document in cursor:
            all_study_students[document["user_id"]] = document["study_expires_at"]
        return all_study_students

    async def delete_study_user(self, user_id: int):
        """Remove a studying user from the database"""
        ...

    # Reminders
    async def get_all_user_reminders(self, user_id: int) -> dict[str, dict[str, Union[str, int]]]:
        """Get all reminders of a particular user"""
        # return a dict of reminders like so:
        # {
        #     "reminder_id": {
        #         "start": "start_time: INT",
        #         "end": "end_time: INT",
        #         "message": "message: STR",
        #     },
        #     "reminder_id": {
        #         "start": "start_time: INT",
        #         "end": "end_time: INT",
        #         "message": "message: STR",
        #     }
        # }
        ...

    async def set_reminder(self, reminder_id: str, user_id: int, start_time: int, end_time: int, message: str = "") -> None:
        """Set a new reminder for a particular user"""
        ...

    async def remove_reminder(self, user_id: int, reminder_id: str) -> None:
        """Remove a particular reminder for a particular user"""
        ...

    async def remove_all_user_reminders(self, user_id: int):
        """Remove all reminders for a particular user"""
        user_config = await self.read_user_config(user_id)
        user_config["reminders"] = []
        await self.update_user_config(user_id, user_config)

    async def get_all_reminders(self) -> dict[str, dict[str, Union[str, int]]]:
        """Get all known reminders in the database"""
        # Return all reminders known to the bot in this format:
        # {
        #     "reminder_id": {
        #         "user_id": "user_id: INT",
        #         "start": "start_time: INT",
        #         "end": "end_time: INT",
        #         "message": "message: STR",
        #     },
        #     "reminder_id": {
        #         "user_id": "user_id: INT",
        #         "start": "start_time: INT",
        #         "end": "end_time: INT",
        #         "message": "message: STR",
        #     }
        # }
        ...

        pipeline = [
            {"$match": {"reminders": {"$exists": True}}},
            {"$unwind": "$reminders"},
            {"$project": {"_id": 0, "user_id": 1, "expires_at": "$reminders.expires_at", "message": "$reminders.message"}},
        ]

        cursor = self.user_config.aggregate(pipeline)
        return list(cursor)

    async def get_modmail_banned_users(self) -> List[int]:
        """Return a list of User IDs which are banned from using Modmail"""
        ...

    async def get_user_modmail_channel(self, user_id: int) -> Optional[int]:
        """Return modmail thread ID if exists, or else return None"""
        ...

    async def set_user_modmail_channel(self, user_id: int, thread_id: int) -> None:
        """Set the modmail thread ID for a particular user"""
        ...

    async def ban_modmail_user(self, user_id: int) -> None:
        """Ban a user from using modmail"""
        ...

    async def unban_modmail_user(self, user_id: int) -> None:
        """Unban a user from using modmail"""
        ...

    async def set_user_appeal_submission(self, user_id: int, submission_time: int, message_id: int) -> None:
        """Set the last known appeal submission time. If already set, replace."""
        ...

    async def get_last_appeal(self, user_id: int):
        """Return last appeal time and decision"""
        # return a tuple of data: (last_appeal_time, last_appeal_decision)
        # last_appeal_time: epoch timestamp of last appeal submission. 0 if not exists
        # last_appeal_decision:
        #       None: Not Decided Yet
        #       True: Unbanned
        #       False: Remains banned
        ...

    async def get_all_pending_decisions(self):
        """Get all the pending ban appeals"""
        # return a list like this:
        # [
        #     [
        #         user_id,
        #         submission_time
        #         message_time
        #     ],
        #     [
        #         user_id,
        #         submission_time
        #         message_time
        #     ]
        # ]


    async def get_decay_date(self) -> datetime:
        # return datetime object
        config = await self.read_user_config(self.bot_user_id)
        return config["decay_day"]

    async def remove_one_inf(self) -> None:
        config = await self.read_user_config(self.bot_user_id)

        await self.user_config.update_many({"infraction_points": {"$gt": 0}}, {"$inc": {"infraction_points": -1}})
        config["decay_day"] = config["decay_day"] + datetime.timedelta(days=7)
