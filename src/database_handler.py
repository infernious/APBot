import os
from dotenv import load_dotenv
load_dotenv()
import random
from datetime import datetime
import logging
from typing import List, Optional, Union
import time
import motor.motor_asyncio as motor

from config_handler import Config

database_client = motor.AsyncIOMotorClient(os.getenv("APBOT_DATABASE_CONNECT_URL"))


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class BaseDatabase(metaclass=SingletonMeta):
    def __init__(self, conf=None):
        self.bot_user_id: int
        self.database = database_client["ap-test"]
        self.user_config = self.database["user_config"]
        self.bot_config = self.database["bot_config"]
        self.ban_appeals = self.database["ban_appeals"]
        self.reminders = self.database["reminders"]
        self.recurrent = self.database["recurrent"]
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
        return await self.bot_config.find_one({"name": name})

    async def update_bot_config(self, new_config):
        if "_id" in new_config:
            await self.bot_config.replace_one({"_id": new_config["_id"]}, new_config)
        else:
            raise AttributeError("No _id present in new config.")


class ModmailDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)

    async def get_banned_users(self) -> List[int]:
        """Return a list of User IDs which are banned from using Modmail"""

        modmail_config = await self.read_bot_config("modmail")
        return modmail_config["banned_users"]

    async def get_channel(self, user_id: int) -> Optional[int]:
        """Return modmail thread ID if exists, or else return None"""

        user_config = await self.read_user_config(user_id)
        return user_config.get("modmail_id")

    async def set_channel(self, user_id: int, thread_id: int) -> None:
        """Set the modmail thread ID for a particular user"""

        user_config = await self.read_user_config(user_id)
        user_config["modmail_id"] = thread_id
        await self.update_user_config(user_id, user_config)

    async def unset_channel(self, user_id: int) -> None:
        """Unset the user's modmail channel"""
        conf = await self.read_user_config(user_id)
        del conf["modmail_id"]
        await self.update_user_config(user_id, conf)

    async def ban_user(self, user_id: int) -> None:
        """Ban a user from using modmail"""

        modmail_config = await self.read_bot_config("modmail")
        if user_id in modmail_config["banned_users"]:
            return

        modmail_config["banned_users"].append(user_id)
        await self.update_bot_config(modmail_config)

    async def unban_user(self, user_id: int) -> None:
        """Unban a user from using modmail"""

        modmail_config = await self.read_bot_config("modmail")
        if user_id not in modmail_config["banned_users"]:
            return

        modmail_config["banned_users"].remove(user_id)
        await self.update_bot_config(modmail_config)


class StudyDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)

    async def set_time(self, user_id: int, study_expires_at: int) -> None:
        """Set the time at which study will expire for a particular user"""

        user_config = await self.read_user_config(user_id)
        user_config["study_expires_at"] = study_expires_at

        await self.update_user_config(user_id, user_config)

    async def get_end_time(self, user_id: int) -> Optional[int]:
        """Get the time at which study expires for a particular user"""

        user_config = await self.read_user_config(user_id)
        return user_config.get("study_expires_at")

    async def get_all(self) -> dict[int, int]:
        """Return all users with the study role"""

        return {document["user_id"]: document["study_expires_at"]
                async for document in self.user_config.find({"study_expires_at": {"$exists": True}})}

    async def delete_user(self, user_id: int):
        """Remove a studying user from the database"""

        user_config = await self.read_user_config(user_id)
        user_config.pop("study_expires_at")

        try:
            await self.update_user_config(user_id, user_config)
        except KeyError:
            pass


class BonkDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)

    async def new(self, reminder_id: str, user_id: int, start_time: int, end_time: int, message: str = "") -> None:
        """Set a new reminder for a particular user"""

        await self.reminders.insert_one(
            {
                "user_id": user_id,
                "reminder_id": reminder_id,
                "start_time": start_time,
                "end_time": end_time,
                "message": message,
            }
        )

    async def remove(self, user_id: int, reminder_id: str) -> None:
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
                "message": document["message"],
            }

        return reminders_dict

    async def remove_all_user_reminders(self, user_id: int):
        """Remove all reminders for a particular user"""
        await self.reminders.delete_many({"user_id": user_id})

    async def get_all(self) -> dict[str, dict[str, Union[str, int]]]:
        """Get all known reminders in the database"""
        cursor = self.reminders.find({})
        reminders_dict = {}

        async for document in cursor:
            reminders_dict[document["reminder_id"]] = {
                "user_id": document["user_id"],
                "start_time": document["start_time"],
                "end_time": document["end_time"],
                "message": document["message"],
            }

        return reminders_dict


class AppealDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)

    async def read_appeal(self, user_id: int):
        config_from_db = await self.ban_appeals.find_one({"user_id": user_id})

        if config_from_db is None:
            config_from_db = {
                "user_id": user_id,
                "submission_time": datetime.now().timestamp(),
                "updates": [],
                "decision": None,
            }
            await self.ban_appeals.insert_one(config_from_db)

        return config_from_db

    async def update_appeal(self, user_id: int, new_config):
        old_config = await self.read_ban_appeal(user_id)
        await self.ban_appeals.replace_one({"_id": old_config["_id"]}, new_config)

    async def set_submission_time(self, user_id: int, submission_time: int) -> None:
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

        return [[document["user_id"], document["submission_time"]] for document in self.ban_appeals.find({"decision": None})]


class RecurrentDatabase(BaseDatabase):

    def __init__(self, conf=None):
        super().__init__(conf)
    async def add_message(self, channel_id: int, message: str, limit: int) -> None:
        channel_dict = await self.recurrent.find_one({"channel_id": channel_id})
        if channel_dict is None:
            channel_dict = {"channel_id": channel_id, "messages": [message], "message_counts": {message: 0}, "limit": limit}
            await self.recurrent.insert_one(channel_dict)
        else:
            if message not in channel_dict["messages"]:
                channel_dict["messages"].append(message)
                channel_dict["message_counts"][message] = 0
            channel_dict["limit"] = limit
            await self.recurrent.update_one({"channel_id": channel_id}, {"$set": {"messages": channel_dict["messages"], "message_counts": channel_dict["message_counts"], "limit": limit}})

    async def get_messages(self, channel_id: int) -> list:
        channel_dict = await self.recurrent.find_one({"channel_id": channel_id})
        return channel_dict["messages"] if channel_dict else []

    async def clear_all_data(self) -> None:
        await self.recurrent.delete_many({})

    async def get_channel_config(self, channel_id: int) -> dict:
        channel_dict = await self.recurrent.find_one({"channel_id": channel_id})
        return channel_dict if channel_dict else {"messages": [], "message_counts": {}, "limit": 0}

    async def remove_message(self, channel_id: int, message: str) -> None:
        await self.recurrent.update_one({"channel_id": channel_id}, {"$pull": {"messages": message}, "$unset": {f"message_counts.{message}": ""}})

    async def update_message_count(self, channel_id: int, message: str, count: int) -> None:
        await self.recurrent.update_one({"channel_id": channel_id}, {"$set": {f"message_counts.{message}": count}})

    async def add_group(self, name: str, channel_ids: list) -> None:
        group_dict = await self.recurrent.find_one({"group_name": name})
        if group_dict is None:
            group_dict = {"group_name": name, "channel_ids": channel_ids}
            await self.recurrent.insert_one(group_dict)
        else:
            group_dict["channel_ids"].extend(channel_ids)
            await self.recurrent.update_one({"group_name": name}, {"$set": {"channel_ids": list(set(group_dict["channel_ids"]))}})

    async def get_groups(self) -> dict:
        groups = await self.recurrent.find({"group_name": {"$exists": True}}).to_list(length=None)
        return {group["group_name"]: group["channel_ids"] for group in groups}

    async def get_group(self, name: str) -> list:
        group_dict = await self.recurrent.find_one({"group_name": name})
        return group_dict["channel_ids"] if group_dict else []

    async def delete_group(self, name: str) -> None:
        await self.recurrent.delete_one({"group_name": name})

    async def clear_channel_messages(self, channel_id: int) -> None:
        await self.recurrent.update_one({"channel_id": channel_id}, {"$set": {"messages": [], "message_counts": {}}})


class Database:
    def __init__(self, conf: Config) -> None:
        base_db = BaseDatabase(conf)
        self.modmail: ModmailDatabase = ModmailDatabase()
        self.study: StudyDatabase = StudyDatabase()
        self.bonk: BonkDatabase = BonkDatabase()
        self.appeal: AppealDatabase = AppealDatabase()
        self.recurrent: RecurrentDatabase = RecurrentDatabase()
