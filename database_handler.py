import json
import os
from datetime import datetime
from typing import List, Optional, Union

import motor.motor_asyncio as motor

from config_handler import Config

database_client = motor.AsyncIOMotorClient(os.environ.get("APBOT_DATABASE_CONNECT_URL"))
class Database:
    def __init__(self, conf: Config):
        self.bot_user_id: int
        self.database = database_client["ap-students"]
        self.user_config = self.database["user_config"]
        self.bot_config = self.database["bot_config"]
        self.ban_appeals = self.database["ban_appeals"]
        self.reminders = self.database["reminders"]
        self.conf = conf

    async def read_user_config(self, user_id: int):
        config_from_db = await self.user_config.find_one({"user_id": user_id})

        if config_from_db is None:
            config_from_db = {"user_id": user_id, "infraction_points": 0, "infractions": []}
            await self.user_config.insert_one(config_from_db)

        return config_from_db

    async def update_user_config(self, user_id: int, new_config):
        old_config = await self.user_config.find_one({"user_id": user_id})

        if old_config is None:
            config = {"user_id": user_id, "infraction_points": 0, "infractions": []}
            old_config = await self.user_config.insert_one(config)

        _id = old_config["_id"]
        await self.user_config.replace_one({"_id": _id}, new_config)

    async def read_bot_config(self, name: str):
        modmail_config = await self.bot_config.find_one({"name": name})
        return modmail_config

    async def update_bot_config(self, new_config):
        if "_id" in new_config:
            await self.bot_config.replace_one({"_id": new_config["_id"]}, new_config)
        else:
            raise AttributeError("No _id present in new config.")

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
        async for document in cursor:
            all_study_students[document["user_id"]] = document["study_expires_at"]
        return all_study_students

    async def delete_study_user(self, user_id: int):
        """Remove a studying user from the database"""
        user_config = await self.read_user_config(user_id)
        user_config.pop("study_expires_at")
        try:
            await self.update_user_config(user_id, user_config)
        except KeyError:
            pass

    # Reminders
    async def set_reminder(self, reminder_id: str, user_id: int, start_time: int, end_time: int, message: str = "") -> None:
        """Set a new reminder for a particular user"""
        reminder_dict = {
            "user_id": user_id,
            "reminder_id": reminder_id,
            "start_time": start_time,
            "end_time": end_time,
            "message": message
        }
        await self.reminders.insert_one(reminder_dict)

    async def remove_reminder(self, user_id: int, reminder_id: str) -> None:
        """Remove a particular reminder for a particular user"""
        await self.reminders.delete_one({"user_id": user_id, "reminder_id": reminder_id})

    async def get_all_user_reminders(self, user_id: int) -> dict[str, dict[str, Union[str, int]]]:
        """Get all reminders of a particular user"""
        cursor = self.reminders.find({"user_id": user_id})
        reminders_dict = {}
        async for document in cursor:
            reminders_dict[document["reminder_id"]] = {
                "start_time": document["start_time"],
                "end_time": document["end_time"],
                "message": document["message"]
            }
        return reminders_dict

    async def remove_all_user_reminders(self, user_id: int):
        """Remove all reminders for a particular user"""
        await self.reminders.delete_many({"user_id": user_id})

    async def get_all_reminders(self) -> dict[str, dict[str, Union[str, int]]]:
        """Get all known reminders in the database"""
        cursor = self.reminders.find({})
        reminders_dict = {}
        async for document in cursor:
            reminders_dict[document["reminder_id"]] = {
                "user_id": document["user_id"],
                "start_time": document["start_time"],
                "end_time": document["end_time"],
                "message": document["message"]
            }
        return reminders_dict

    # Modmail
    async def get_modmail_banned_users(self) -> List[int]:
        """Return a list of User IDs which are banned from using Modmail"""
        modmail_config = await self.read_bot_config("modmail")
        return modmail_config["banned_users"]

    async def get_user_modmail_channel(self, user_id: int) -> Optional[int]:
        """Return modmail thread ID if exists, or else return None"""
        user_config = await self.read_user_config(user_id)
        if "modmail_id" in user_config:
            return user_config["modmail_id"]
        else:
            return None

    async def set_user_modmail_channel(self, user_id: int, thread_id: int) -> None:
        """Set the modmail thread ID for a particular user"""
        user_config = await self.read_user_config(user_id)
        user_config["modmail_id"] = thread_id
        await self.update_user_config(user_id, user_config)

    async def ban_modmail_user(self, user_id: int) -> None:
        """Ban a user from using modmail"""
        modmail_config = await self.read_bot_config("modmail")
        modmail_config["banned_users"].append(user_id)
        await self.update_bot_config(modmail_config)

    async def unban_modmail_user(self, user_id: int) -> None:
        """Unban a user from using modmail"""
        modmail_config = await self.read_bot_config("modmail")
        modmail_config["banned_users"].pop(user_id)
        await self.update_bot_config(modmail_config)

    # Ban Appeals
    async def read_ban_appeal(self, user_id: int):
        config_from_db = await self.ban_appeals.find_one({"user_id": user_id})

        if config_from_db is None:
            config_from_db = {
                "user_id": user_id,
                "submission_time": datetime.datetime.now().timestamp(),
                "updates": [],
                "decision": None
            }
            await self.ban_appeals.insert_one(config_from_db)

        return config_from_db

    async def update_ban_appeal(self, user_id: int, new_config):
        old_config = await self.ban_appeals.find_one({"user_id": user_id})

        if old_config is None:
            old_config = {
                "user_id": user_id,
                "submission_time": datetime.datetime.now().timestamp(),
                "updates": [],
                "decision": None
            }
            await self.ban_appeals.insert_one(old_config)

        _id = old_config["_id"]
        await self.ban_appeals.replace_one({"_id": _id}, new_config)

    async def set_user_appeal_submission(self, user_id: int, submission_time: int, message_id: int) -> None:
        """Set the last known appeal submission time. If already set, replace."""
        ban_appeal = await self.read_ban_appeal(user_id)
        ban_appeal["submission_time"] = submission_time
        await self.update_ban_appeal(user_id, ban_appeal)

    async def get_last_appeal(self, user_id: int):
        """Return last appeal time and decision"""
        # return a tuple of data: (last_appeal_time, last_appeal_decision)
            # last_appeal_time: epoch timestamp of last appeal submission. 0 if not exists
        # last_appeal_decision:
        #       None: Not Decided Yet
        #       True: Unbanned
        #       False: Remains banned
        ban_appeal = await self.read_ban_appeal(user_id)
        last_appeal = (ban_appeal["submission_time"], ban_appeal["decision"])
        return last_appeal

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
        cursor = self.ban_appeals.find({"decision": None})
        pending_decisions = []
        for document in cursor:
            pending_decisions.append([document["user_id"], document["submission_time"]])
        return list(cursor)

    async def get_decay_date(self) -> datetime:
        # return datetime object
        config = await self.read_user_config(self.bot_user_id)
        return config["decay_day"]

    async def remove_one_inf(self) -> None:
        config = await self.read_user_config(self.bot_user_id)
        await self.user_config.update_many({"infraction_points": {"$gt": 0}}, {"$inc": {"infraction_points": -1}})
        config["decay_day"] = config["decay_day"] + datetime.timedelta(days=7)
