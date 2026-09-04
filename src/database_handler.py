import os
from dotenv import load_dotenv
load_dotenv()
import random
from datetime import datetime, timedelta
from datetime import timezone
import asyncio
from typing import List, Optional, Union
import time
import motor.motor_asyncio as motor
import sqlite3
from config_handler import Config
database_client = motor.AsyncIOMotorClient(os.getenv("APBOT_DATABASE_CONNECT_URL"))
from models import Infraction
import logging
from typing import Optional
import re
logger = logging.getLogger(__name__)
DISCORD_EPOCH_MS = 1420070400000
DURATION_UNITS = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
    "w": 604800,
    "week": 604800,
    "weeks": 604800,
}
MAX_TIMEOUT_DURATION_SECONDS = 28 * 86400


def is_possible_snowflake(value: int) -> bool:
    text = str(value)
    if not 17 <= len(text) <= 20:
        return False

    created_ms = (value >> 22) + DISCORD_EPOCH_MS
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return DISCORD_EPOCH_MS <= created_ms <= now_ms + 86400000


def first_snowflake(value):
    if value is None:
        return None

    if hasattr(value, "id"):
        value = value.id

    text = str(value)

    for pattern in (r"<@!?(\d{17,20})>", r"(?<!\d)(\d{17,20})(?!\d)"):
        match = re.search(pattern, text)

        if match:
            candidate = int(match.group(1))

            if is_possible_snowflake(candidate):
                return candidate

    for match in re.finditer(r"\d{18,}", text):
        digits = match.group(0)

        for size in range(min(20, len(digits) - 1), 16, -1):
            for candidate_text in (digits[:size], digits[-size:]):
                candidate = int(candidate_text)

                if is_possible_snowflake(candidate):
                    return candidate

        for size in range(min(20, len(digits) - 1), 16, -1):
            for start in range(1, len(digits) - size):
                candidate = int(digits[start:start + size])

                if is_possible_snowflake(candidate):
                    return candidate

    return None


def parse_duration_string(value: str) -> Optional[int]:
    text = value.strip().lower()

    if not text:
        return None

    if text.isdigit():
        duration = int(text)
        return duration if duration > 0 else None

    time_parts = text.split(":")
    if 2 <= len(time_parts) <= 3 and all(part.isdigit() for part in time_parts):
        numbers = [int(part) for part in time_parts]

        if len(numbers) == 2:
            minutes, seconds = numbers
            duration = minutes * 60 + seconds
            return duration if duration > 0 else None

        hours, minutes, seconds = numbers
        duration = hours * 3600 + minutes * 60 + seconds
        return duration if duration > 0 else None

    day_prefix = 0
    day_match = re.match(r"^(\d+)\s+days?,\s*(.+)$", text)

    if day_match:
        day_prefix = int(day_match.group(1)) * 86400
        text = day_match.group(2)
        time_duration = parse_duration_string(text)
        return day_prefix + time_duration if time_duration is not None else None

    matches = list(
        re.finditer(
            r"(\d+(?:\.\d+)?)\s*(weeks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)",
            text,
        )
    )

    if not matches:
        return None

    leftovers = re.sub(
        r"(\d+(?:\.\d+)?)\s*(weeks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)",
        "",
        text,
    )
    leftovers = re.sub(r"[\s,;:+-]", "", leftovers)

    if leftovers:
        return None

    total = 0

    for match in matches:
        amount, unit = match.groups()
        total += float(amount) * DURATION_UNITS[unit]

    duration = int(total)
    return duration if duration > 0 else None


def normalize_duration(value) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, timedelta):
        duration = int(value.total_seconds())
        return duration if duration > 0 else None

    if isinstance(value, (int, float)):
        duration = int(value)

        if duration <= 0:
            return None

        if duration > MAX_TIMEOUT_DURATION_SECONDS and duration % 1000 == 0:
            duration_ms = duration // 1000

            if 0 < duration_ms <= MAX_TIMEOUT_DURATION_SECONDS:
                return duration_ms

        return duration

    if isinstance(value, str):
        return parse_duration_string(value)

    return None


def normalize_duration_milliseconds(value) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, str) and not value.strip().isdigit():
        return normalize_duration(value)

    try:
        duration = int(value)
    except (TypeError, ValueError):
        return None

    if duration <= 0:
        return None

    duration_seconds = duration // 1000
    return duration_seconds if duration_seconds > 0 else None


def normalize_actiontype(value) -> str:
    action = str(value or "unknown").strip().lower().replace("_", "-")
    action = re.sub(r"\s+", "-", action)

    aliases = {
        "wm": "mute",
        "warn-mute": "mute",
        "warnmute": "mute",
        "warning-mute": "mute",
        "pseudomute": "pseudo-mute",
        "pseudo-mute": "pseudo-mute",
        "forceban": "force-ban",
        "force-ban": "force-ban",
        "internal-note": "note",
    }

    return aliases.get(action, action or "unknown")


def normalize_attachment(value):
    if value is None:
        return None

    if isinstance(value, (list, tuple)):
        for item in value:
            normalized = normalize_attachment(item)

            if normalized:
                return normalized

        return None

    if isinstance(value, dict):
        return normalize_attachment(
            value.get("url")
            or value.get("proxy_url")
            or value.get("attachment_url")
            or value.get("filename")
        )

    text = str(value).strip()
    return text or None


def legacy_unmute_update(infraction: dict):
    moderator = (
        infraction.get("unmute_moderator")
        or infraction.get("unmuted_by")
        or infraction.get("unmute_mod")
    )
    reason = (
        infraction.get("unmute_reason")
        or infraction.get("unmuted_reason")
        or infraction.get("unmute_note")
    )

    if not moderator and not reason:
        return None

    return {
        "moderator": moderator or "Unknown moderator",
        "update": f"Unmuted: {reason or 'No reason provided'}",
        "date": (
            infraction.get("unmute_date")
            or infraction.get("unmuted_at")
            or infraction.get("unmute_time")
            or infraction.get("date")
            or infraction.get("actiontime")
        ),
    }


def normalize_updates(value) -> list:
    if not value:
        return []

    if isinstance(value, list):
        return list(value)

    if isinstance(value, tuple):
        return list(value)

    return [value]



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
        self.tags = self.database["tags"]
        self.conf = conf


    async def add_inf_points(self, user_id: int, points: int) -> Optional[int]:
        try:
            # Read the current user configuration
            user_config = await self.read_user_config(user_id)

            # Calculate new infraction points
            new_points = user_config.get("infraction_points", 0) + points
            user_config["infraction_points"] = new_points

            # Update the user's configuration in the database
            await self.update_user_config(user_id, user_config)

            # Return the updated points
            return new_points

        except Exception as e:
            print(f"Error updating infraction points for user_id {user_id}: {e}")
            return None


    async def read_user_config(self, user_id: int):
        config_from_db = await self.user_config.find_one({"user_id": user_id})

        if config_from_db is None:
            config_from_db = {"user_id": user_id, "infraction_points": 0, "infractions": []}
            await self.user_config.insert_one(config_from_db)

        return config_from_db

    async def update_user_config(self, user_id: int, new_config):
        try:
            old_config = await self.user_config.find_one({"user_id": user_id})

            if old_config is None:
                # If there is no old config, insert a new one
                await self.user_config.insert_one(new_config)
            else:
                # Otherwise, replace the old config with the new one
                _id = old_config["_id"]
                await self.user_config.replace_one({"_id": _id}, new_config)

        except Exception as e:
            # Log any errors that occur during the update
            print(f"Error updating user config for user_id {user_id}: {e}")

    async def delete_all_user_data(self, user_id: int) -> dict[str, int]:
        """Permanently remove MongoDB data directly linked to a Discord user.

        This intentionally does not touch Discord messages, native bans,
        timeouts, roles, or audit logs. References to the requester acting as a
        moderator are anonymized so deleting one moderator does not erase
        another member's moderation record.
        """
        user_ids = [user_id, str(user_id)]
        collections = {
            "user_config": self.user_config,
            "reminders": self.reminders,
            "ban_appeals": self.ban_appeals,
            "tags": self.tags,
            "emergency_usage": self.database["emergency_usage"],
            "temporary_restrictions": self.database["temporary_restrictions"],
            "media_levels": self.database["media_levels"],
            # Keep this cleanup even if the Wordle feature is later disabled so
            # legacy records can still be erased.
            "wordle_results": self.database["wordle_results"],
        }

        deleted: dict[str, int] = {}
        for name, collection in collections.items():
            result = await collection.delete_many({"user_id": {"$in": user_ids}})
            deleted[name] = result.deleted_count

        channel_result = await self.database["channel_config"].delete_many(
            {"modmail_user_id": {"$in": user_ids}}
        )
        deleted["modmail_mappings"] = channel_result.deleted_count

        modmail_result = await self.bot_config.update_one(
            {"name": "modmail"},
            {"$pull": {"banned_users": {"$in": user_ids}}},
        )
        deleted["modmail_block_entries"] = modmail_result.modified_count

        restriction_result = await self.database["temporary_restrictions"].update_many(
            {"moderator_id": {"$in": user_ids}},
            {"$set": {"moderator_id": None}},
        )
        deleted["restriction_moderator_references_anonymized"] = (
            restriction_result.modified_count
        )

        deleted["infraction_moderator_references_anonymized"] = (
            await self._anonymize_infraction_moderator_references(user_id)
        )
        return deleted

    async def _anonymize_infraction_moderator_references(self, user_id: int) -> int:
        """Remove a moderator's ID from other users' infraction histories."""
        changed_documents = 0
        cursor = self.user_config.find(
            {
                "$or": [
                    {"infractions.moderator": {"$in": [user_id, str(user_id)]}},
                    {"infractions.update.moderator": {"$in": [user_id, str(user_id)]}},
                ]
            }
        )

        async for document in cursor:
            changed = False
            for infraction in document.get("infractions", []):
                if not isinstance(infraction, dict):
                    continue

                if first_snowflake(infraction.get("moderator")) == user_id:
                    infraction["moderator"] = 0
                    changed = True

                updates = infraction.get("update")
                if isinstance(updates, dict):
                    updates = [updates]
                    infraction["update"] = updates

                if not isinstance(updates, list):
                    continue

                for update in updates:
                    if (
                        isinstance(update, dict)
                        and first_snowflake(update.get("moderator")) == user_id
                    ):
                        update["moderator"] = 0
                        changed = True

            if changed:
                await self.user_config.replace_one(
                    {"_id": document["_id"]},
                    document,
                )
                changed_documents += 1

        return changed_documents
            
    async def add_infraction(self, user_id: int, infraction: Infraction):
        user_config = await self.read_user_config(user_id)
        user_config.setdefault("infractions", [])

        # moderator can be Member or int
        moderator_id = infraction.moderator.id if hasattr(infraction.moderator, "id") else int(infraction.moderator)

        # actiontime: store UTC ISO with tzinfo
        if isinstance(infraction.actiontime, datetime):
            dt = infraction.actiontime
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)  # assume legacy naive is UTC
            actiontime_iso = dt.astimezone(timezone.utc).isoformat()
        else:
            actiontime_iso = datetime.now(timezone.utc).isoformat()

        user_config["infractions"].append({
            "actiontype": infraction.actiontype,          
            "reason": infraction.reason,
            "moderator": moderator_id,
            "actiontime": actiontime_iso,
            "duration": infraction.duration,
            "attachment_url": infraction.attachment_url,
            "update": infraction.update if hasattr(infraction, "update") else [],
        })

        await self.update_user_config(user_id, user_config)
        # Award points only for /mute
        if infraction.actiontype.lower() == "mute" and infraction.duration:
            hours = infraction.duration / 3600  # convert seconds → hours
            if hours >= 25:
                points = 20
            elif hours >= 12:
                points = 15
            elif hours >= 6:
                points = 10
            elif hours >= 3:
                points = 5
            else:
                points = 0

            if points > 0:
                await self.add_inf_points(user_id, points)
                print(f"[DB] Added {points} infraction points to {user_id} for a {hours:.1f}h wm.")




    async def update_infraction_reason(self, user_id: int, index: int, reason: str) -> bool:
        user_config = await self.read_user_config(user_id)
        infractions = user_config.get("infractions", [])

        if index < 1 or index > len(infractions):
            return False

        infraction = infractions[index - 1]
        infraction["reason"] = reason
        infraction["mute_reason"] = reason
        await self.update_user_config(user_id, user_config)
        return True

    async def delete_infraction(self, user_id: int, index: int) -> bool:
        user_config = await self.read_user_config(user_id)
        infractions = user_config.get("infractions", [])

        if index < 1 or index > len(infractions):
            return False

        del infractions[index - 1]
        user_config["infractions"] = infractions
        await self.update_user_config(user_id, user_config)
        return True

    async def add_infraction_note(self, user_id: int, index: int, moderator_id: int, note: str, actiontime=None) -> bool:
        user_config = await self.read_user_config(user_id)
        infractions = user_config.get("infractions", [])

        if index < 1 or index > len(infractions):
            return False

        if actiontime is None:
            actiontime = datetime.now(timezone.utc)

        if isinstance(actiontime, datetime):
            if actiontime.tzinfo is None:
                actiontime = actiontime.replace(tzinfo=timezone.utc)
            actiontime = actiontime.astimezone(timezone.utc).isoformat()

        infraction = infractions[index - 1]
        updates = normalize_updates(infraction.get("update"))
        updates.append({
            "moderator": moderator_id,
            "update": note,
            "date": actiontime,
        })
        infraction["update"] = updates

        await self.update_user_config(user_id, user_config)
        return True

    async def get_user_infractions(self, user_id: int) -> list:
        user_config = await self.read_user_config(user_id)
        infractions = user_config.get("infractions", [])

        def first_value(*values):
            for value in values:
                if value is not None:
                    return value
            return None

        def normalize_time(value):
            if isinstance(value, datetime):
                dt = value
            elif isinstance(value, (int, float)):
                dt = datetime.fromtimestamp(value, timezone.utc)
            elif isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except Exception:
                    dt = datetime.now(timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(timezone.utc)

        def normalize_moderator(value):
            if value is None:
                return 0

            moderator_id = first_snowflake(value)

            if moderator_id is not None:
                return moderator_id

            return value

        cleaned_infractions = []

        for inf in infractions:
            updates = normalize_updates(
                inf.get("update") if inf.get("update") is not None else inf.get("updates")
            )
            unmute_update = legacy_unmute_update(inf)

            if unmute_update:
                updates.append(unmute_update)

            duration = normalize_duration(
                first_value(
                    inf.get("duration"),
                    inf.get("mute_duration"),
                    inf.get("mute_length"),
                    inf.get("mute_time"),
                    inf.get("duration_seconds"),
                    inf.get("mute_duration_seconds"),
                    inf.get("length"),
                )
            )
            duration_ms = normalize_duration_milliseconds(
                first_value(
                    inf.get("duration_ms"),
                    inf.get("mute_duration_ms"),
                    inf.get("length_ms"),
                )
            )

            cleaned = {
                "actiontype": normalize_actiontype(first_value(inf.get("actiontype"), inf.get("type"), "unknown")),
                "reason": first_value(inf.get("reason"), inf.get("mute_reason"), "No reason provided"),
                "moderator": normalize_moderator(first_value(inf.get("moderator"), inf.get("mute_moderator"), 0)),
                "actiontime": normalize_time(first_value(inf.get("actiontime"), inf.get("date"))),
                "duration": duration if duration is not None else duration_ms,
                "attachment_url": normalize_attachment(
                    first_value(
                        inf.get("attachment_url"),
                        inf.get("attachment"),
                        inf.get("attachments"),
                        inf.get("evidence"),
                        inf.get("image_url"),
                    )
                ),
                "update": updates,
            }

            cleaned_infractions.append(Infraction(**cleaned))

        return cleaned_infractions

    async def read_bot_config(self, name: str):
        return await self.bot_config.find_one({"name": name})

    async def update_bot_config(self, new_config):
        # If in the new config has a properly constructed _id, simply replace the old _id with the new one
        if "_id" in new_config and new_config["_id"]:
            await self.bot_config.replace_one({"_id": new_config["_id"]}, new_config)
        # Otherwise, insert a properly constructured _id into the passed in new config
        else:
            await self.bot_config.replace_one(
            {"name": new_config["name"]},
            new_config,
            upsert=True
        )
    async def _read_config_file(self, type_: str, id_: int) -> dict:
        """Fallback dummy or real method for config reading."""
        # Example using user_config or a placeholder, depending on your system:
        if type_ == "channel":
            return await self.database["channel_config"].find_one({"channel_id": id_}) or {}
        elif type_ == "user":
            return await self.read_user_config(id_)
        return {}
    async def get_inf_points(self, user_id: int) -> Optional[int]:
        try:
            user_config = await self.read_user_config(user_id)
            return user_config.get("infraction_points", 0)
        except Exception as e:
            print(f"Error fetching infraction points for user_id {user_id}: {e}")
            return None
class InfractionDatabase:
    def __init__(self, db_connection):
        self.db = db_connection

    async def get_user_infractions(self, user_id: int):
        # return a list of Infraction objects (or dicts)
        ...
class EmergencyDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)
        self.emergency = self.database["emergency_usage"]

    async def log_usage(self, user_id: int) -> None:
        """Record an emergency usage event and set a 5-minute timeout."""
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=5)  # ⏰ Changed from 24 hours to 5 minutes

        await self.emergency.update_one(
            {"user_id": user_id},
            {"$set": {
                "last_used": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "notified": False
            }},
            upsert=True
        )

    async def is_on_cooldown(self, user_id: int) -> bool:
        """Check if the user is still within their 5-minute timeout."""
        doc = await self.emergency.find_one({"user_id": user_id})
        if not doc or "expires_at" not in doc:
            return False

        expires_at = datetime.fromisoformat(doc["expires_at"])
        return datetime.utcnow() < expires_at

    async def set_notified(self, user_id: int):
        """Mark user as notified (after sending DM)."""
        await self.emergency.update_one({"user_id": user_id}, {"$set": {"notified": True}})

    async def get_expired_users(self) -> list[int]:
        """Return list of users whose cooldowns expired (for cleanup)."""
        now = datetime.utcnow()
        cursor = self.emergency.find({"expires_at": {"$lte": now}})
        return [doc["user_id"] async for doc in cursor]

    async def clear_expired(self):
        """Remove expired cooldown entries."""
        now = datetime.utcnow()
        await self.emergency.delete_many({"expires_at": {"$lte": now}})

    async def can_use(self, user_id: int, db) -> tuple[bool, str]:
        now = datetime.utcnow()

        # 1) Check if user is banned from modmail
        banned_users = await db.modmail.get_banned_users()
        if user_id in banned_users:
            return False, "You are banned from using this command."

        # 2) Check emergency cooldown
        doc = await self.emergency.find_one({"user_id": user_id})
        emergency_end = None
        if doc and "expires_at" in doc:
            try:
                emergency_end = datetime.fromisoformat(doc["expires_at"])
            except:
                emergency_end = None

        # 3) Check mute cooldown (from infractions), capped at 5 minutes
        infractions = await db.base_db.get_user_infractions(user_id)
        mute_end = None

        for inf in infractions:
            # ensure actiontime is parsed correctly
            if isinstance(inf.actiontime, str):
                try:
                    inf.actiontime = datetime.fromisoformat(inf.actiontime.replace("Z", "+00:00"))
                except:
                    inf.actiontime = now

            if inf.actiontype.lower() in ("mute", "wm") and inf.duration:
                end_time = inf.actiontime + timedelta(seconds=inf.duration)
                # cap mute cooldown at 5 min max
                end_time_capped = min(end_time, now + timedelta(minutes=5))
                if end_time_capped > now:
                    if not mute_end or end_time_capped > mute_end:
                        mute_end = end_time_capped

        # 4) If no cooldowns at all
        if not mute_end and not emergency_end:
            return True, ""

        # Determine the latest active cooldown
        final_end = max(x for x in [mute_end, emergency_end] if x)

        # ✅ FIX: if cooldown already expired → allow
        if final_end < now:
            return True, ""

        # Calculate remaining
        remaining_seconds = int((final_end - now).total_seconds())

        # Cap displayed cooldown message at 5 minutes max
        if remaining_seconds > 5 * 60:
            remaining_seconds = 5 * 60
            final_end = now + timedelta(seconds=remaining_seconds)

        # Return cooldown message
        return False, (
            f"You are on cooldown for <t:{int(final_end.timestamp())}:R>.\n"
            f"This may be because you recently used /emergency or are muted."
        )




    async def clear_cooldown(self, user_id: int):
        await self.emergency.delete_one({"user_id": user_id})

class EmergencyDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)
        self.emergency = self.database["emergency_usage"]

    async def set_cooldown(self, user_id: int, minutes: int = 5):
        """Start or reset the emergency cooldown."""
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=minutes)

        await self.emergency.update_one(
            {"user_id": user_id},
            {"$set": {"expires_at": expires_at.isoformat()}},
            upsert=True
        )

    async def is_on_cooldown(self, user_id: int) -> Optional[int]:
        """Return UNIX timestamp of cooldown end, or None."""
        doc = await self.emergency.find_one({"user_id": user_id})
        if not doc:
            return None

        expires_at = datetime.fromisoformat(doc["expires_at"])
        if datetime.utcnow() >= expires_at:
            await self.emergency.delete_one({"user_id": user_id})
            return None

        return int(expires_at.timestamp())

    async def can_use(self, user_id: int, db) -> tuple[bool, str]:
        # 🚫 Hard ban check
        if user_id in await db.modmail.get_banned_users():
            return False, "You are banned from using this command."

        cooldown_until = await self.is_on_cooldown(user_id)
        if cooldown_until:
            remaining = max(0, cooldown_until - int(datetime.utcnow().timestamp()))

            hours, rem = divmod(remaining, 3600)
            minutes, seconds = divmod(rem, 60)

            if hours > 0:
                time_str = f"{hours}h {minutes}m {seconds}s"
            else:
                time_str = f"{minutes}m {seconds}s"

            return False, (
                f"⏳ You are on cooldown for **{time_str}**.\n"
                "This may be because you recently used /emergency or were muted."
            )



        return True, "" 
    async def clear_cooldown(self, user_id: int):
        await self.emergency.delete_one({"user_id": user_id})


class DecayDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)

    async def set_decay_date(self, dt: datetime):
        await self.bot_config.update_one(
            {"name": "infraction_decay"},
            {"$set": {"next_decay": dt.isoformat()}},
            upsert=True
        )

    async def get_decay_date(self) -> datetime:
        config = await self.bot_config.find_one({"name": "infraction_decay"})
        if config and "next_decay" in config:
            try:
                # Replace 'Z' with '+00:00' to handle UTC timezone string
                decay_str = config["next_decay"].replace("Z", "+00:00")
                return datetime.fromisoformat(decay_str)
            except Exception as e:
                print(f"[DECAY] Error parsing next_decay: {e}")
                return datetime.utcnow()
        else:
            return datetime.utcnow()

    async def remove_one_inf(self) -> Optional[datetime]:
        try:
            # Reduce infraction points
            await self.user_config.update_many(
                {"infraction_points": {"$gt": 0}},
                {"$inc": {"infraction_points": -1}}
            )

            # Calculate new decay date
            new_decay = datetime.utcnow() + timedelta(days=7)

            # Update bot config
            await self.bot_config.update_one(
                {"name": "infraction_decay"},
                {"$set": {"next_decay": new_decay.isoformat()}},
                upsert=True
            )

            return new_decay

        except Exception as e:
            print(f"[DECAY] Failed to apply decay: {e}")
            return None
        
    async def get_last_decay_date(self) -> Optional[datetime]:
        config = await self.bot_config.find_one({"name": "infraction_decay"})
        if config and "last_decay" in config:
            try:
                return datetime.fromisoformat(config["last_decay"])
            except Exception as e:
                print(f"[DECAY] Error parsing last_decay: {e}")
        return None

    async def set_last_decay_date(self, time: datetime):
        await self.bot_config.update_one(
            {"name": "infraction_decay"},
            {"$set": {"last_decay": time.isoformat()}},
            upsert=True
        )


    
class ModmailDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)
        # Initialize all collections we'll use
        self.channel_config = self.database["channel_config"]
        self.user_config = self.database["user_config"]
        self.bot_config = self.database["bot_config"]

    async def get_banned_users(self) -> List[int]:
        modmail_config = await self.bot_config.find_one({"name": "modmail"})
        if not modmail_config:
            return []
        return modmail_config.get("banned_users", [])

    async def get_channel(self, user_id: int) -> Optional[int]:
        user_config = await self.user_config.find_one({"user_id": user_id})
        return user_config.get("modmail_id") if user_config else None

    async def set_channel(self, user_id: int, thread_id: int) -> None:
        await self.user_config.update_one(
            {"user_id": user_id},
            {"$set": {"modmail_id": thread_id}},
            upsert=True
        )

    async def unset_channel(self, user_id: int) -> None:
        await self.user_config.update_one(
            {"user_id": user_id},
            {"$unset": {"modmail_id": ""}}
        )

    async def ban_user(self, user_id: int) -> bool:
        result = await self.bot_config.update_one(
            {"name": "modmail"},
            {"$addToSet": {"banned_users": user_id}},
            upsert=True
        )
        return result.modified_count > 0

    async def unban_user(self, user_id: int) -> bool:
        result = await self.bot_config.update_one(
            {"name": "modmail"},
            {"$pull": {"banned_users": user_id}}
        )
        return result.modified_count > 0

    async def set_user(self, thread_id: int, user_id: int) -> None:
        await self.channel_config.update_one(
            {"channel_id": thread_id},
            {"$set": {"modmail_user_id": user_id}},
            upsert=True
        )

    async def get_user(self, thread_id: int) -> Optional[int]:
        config = await self.channel_config.find_one({"channel_id": thread_id})
        return config.get("modmail_user_id") if config else None




class StudyDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)

    async def set_time(self, user_id: int, study_expires_at: int) -> None:
        """Set the time at which study will expire for a particular user"""
        logger.info(f"Setting study time for user {user_id} to expire at {study_expires_at}")
        user_config = await self.read_user_config(user_id)
        user_config["study_expires_at"] = study_expires_at
        await self.update_user_config(user_id, user_config)
        logger.info(f"Study time set successfully for user {user_id}")

    async def get_end_time(self, user_id: int) -> Optional[int]:
        """Get the time at which study expires for a particular user"""
        user_config = await self.read_user_config(user_id)
        end_time = user_config.get("study_expires_at")
        logger.info(f"Retrieved study end time for user {user_id}: {end_time}")
        return end_time

    async def get_all(self) -> dict[int, int]:
        """Return all users with the study role"""
        logger.info("Fetching all users with study role")
        users_with_study_role = {document["user_id"]: document["study_expires_at"]
                                 async for document in self.user_config.find({"study_expires_at": {"$exists": True}})}
        logger.info(f"Users fetched: {users_with_study_role}")
        return users_with_study_role

    async def delete_user(self, user_id: int):
        """Remove a studying user from the database"""
        logger.info(f"Deleting study role from user {user_id}")
        user_config = await self.read_user_config(user_id)
        if "study_expires_at" in user_config:
            user_config.pop("study_expires_at")
            await self.update_user_config(user_id, user_config)
            logger.info(f"Study role removed for user {user_id}")
        else:
            logger.warning(f"No study role found for user {user_id} to remove")


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
                "updates": [],
            }
            insert_result = await self.ban_appeals.insert_one(config_from_db)
            config_from_db["_id"] = insert_result.inserted_id  # ✅ Ensure _id is present

        return config_from_db


    async def update_appeal(self, user_id: int, new_config):
        old_config = await self.read_appeal(user_id)
        await self.ban_appeals.replace_one({"_id": old_config["_id"]}, new_config)

    async def set_submission_time(self, user_id: int, submission_time: int) -> None:
        ban_appeal = await self.read_appeal(user_id)
        ban_appeal["submission_time"] = submission_time
        await self.update_appeal(user_id, ban_appeal)

    async def get_last_appeal(self, user_id: int):
        ban_appeal = await self.read_appeal(user_id)
        return (
            ban_appeal.get("submission_time"),
            ban_appeal.get("decision")
        )


    async def get_pending_decision(self, user_id: int):
        doc = await self.ban_appeals.find_one({"user_id": user_id, "decision": None})
        if doc and doc.get("message_id"):
            return {
                "submission_time": doc["submission_time"],
                "message_id": doc["message_id"]
            }
        return None

    async def set_message_id(self, user_id: int, message_id: int) -> None:
        ban_appeal = await self.read_appeal(user_id)
        ban_appeal["message_id"] = message_id
        await self.update_appeal(user_id, ban_appeal) 

    async def get_pending_decisions(self):
        """
        Returns a dict of {user_id: (submission_time, message_id)} for all appeals that have no decision.
        """
        pending = await self.ban_appeals.find({"decision": None}).to_list(length=None)
        return {
            doc["user_id"]: (doc["submission_time"], doc.get("message_id"))
            for doc in pending if doc.get("message_id") is not None
        }

    async def set_last_appeal(self, user_id: int, timestamp: float, decision: Optional[bool]) -> None:
        ban_appeal = await self.read_appeal(user_id)
        ban_appeal["submission_time"] = timestamp
        ban_appeal["decision"] = decision
        await self.update_appeal(user_id, ban_appeal)
    async def reset_appeal_state(self, user_id: int, submission_time: float, message_id: int) -> None:
        ban_appeal = await self.read_appeal(user_id)
        ban_appeal["submission_time"] = submission_time
        ban_appeal["decision"] = None
        ban_appeal["message_id"] = message_id
        await self.update_appeal(user_id, ban_appeal)






class TagsDatabase(BaseDatabase):

    def __init__(self, conf=None):
        super().__init__(conf)

    async def exists(self, guild_id: int, user_id: int, name: str) -> bool:
        tag = await self.tags.find_one({"guild_id": guild_id, "user_id": user_id, "name": name})
        return tag is not None

    async def create(self, guild_id: int, user_id: int, name: str, content: str, image_url: Optional[str] = None) -> None:
        tag_dict = await self.tags.find_one({"guild_id": guild_id, "user_id": user_id, "name": name})
        if tag_dict is not None:
            raise ValueError("Tag with this name already exists.")

        await self.tags.insert_one({
            "guild_id": guild_id,
            "user_id": user_id,
            "name": name,
            "content": content,
            "image_url": image_url,
        })

    async def delete(self, guild_id: int, user_id: int, name: str) -> None:
        await self.tags.delete_one({"guild_id": guild_id, "user_id": user_id, "name": name})

    async def update(self, guild_id: int, user_id: int, name: str, new_content: str, image_url: Optional[str] = None) -> None:
        await self.tags.update_one(
            {"guild_id": guild_id, "user_id": user_id, "name": name},
            {"$set": {"content": new_content, "image_url": image_url}},
        )

    async def get_all(self, guild_id: int, user_id: int) -> list:
        tags = await self.tags.find({"guild_id": guild_id, "user_id": user_id}).to_list(length=None)
        return sorted(tags, key=lambda tag: tag.get("name", ""))

    async def get_tag(self, guild_id: int, user_id: int, name: str) -> Optional[dict]:
        return await self.tags.find_one({"guild_id": guild_id, "user_id": user_id, "name": name})

    async def clear_all_tags(self) -> None:
        await self.tags.delete_many({})

    async def remove_user_tags(self, user_id: int) -> None:
        await self.tags.delete_many({"user_id": user_id})
    


class WordleDatabase(BaseDatabase):
    def __init__(self, conf=None):
        super().__init__(conf)
        self.wordle_seasons = self.database["wordle_seasons"]
        self.wordle_results = self.database["wordle_results"]

    async def start_season(self, guild_id: int, channel_id: int, start_date: str, end_date: str) -> None:
        await self.wordle_seasons.update_many(
            {"guild_id": guild_id, "active": True},
            {"$set": {"active": False}},
        )
        await self.wordle_seasons.insert_one({
            "guild_id": guild_id,
            "channel_id": channel_id,
            "start_date": start_date,
            "end_date": end_date,
            "active": True,
        })

    async def get_active_season(self, guild_id: int):
        return await self.wordle_seasons.find_one({"guild_id": guild_id, "active": True})

    async def set_last_summary_message(self, guild_id: int, message_id: int) -> None:
        await self.wordle_seasons.update_one(
            {"guild_id": guild_id, "active": True},
            {"$set": {"last_summary_message_id": message_id}},
        )

    async def save_result(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        username: str,
        puzzle,
        tries,
        failed: bool,
        hard_mode: bool,
        score: int,
        played_date: str,
        message_id: int,
        season_start: str,
        season_end: str,
        source: str,
    ) -> None:
        base_query = {
            "guild_id": guild_id,
            "user_id": user_id,
            "season_start": season_start,
            "season_end": season_end,
        }
        query = dict(base_query)
        if puzzle is not None:
            query["puzzle"] = puzzle
        else:
            query["played_date"] = played_date

        existing = await self.wordle_results.find_one(query)
        if not existing and puzzle is not None:
            query = dict(base_query)
            query["played_date"] = played_date
            existing = await self.wordle_results.find_one(query)

        if existing and existing.get("source") == "wordle_bot_summary" and source != "wordle_bot_summary":
            return

        await self.wordle_results.update_one(
            query,
            {
                "$set": {
                    "channel_id": channel_id,
                    "username": username,
                    "puzzle": puzzle,
                    "tries": tries,
                    "failed": failed,
                    "hard_mode": hard_mode,
                    "score": score,
                    "played_date": played_date,
                    "message_id": message_id,
                    "season_start": season_start,
                    "season_end": season_end,
                    "source": source,
                }
            },
            upsert=True,
        )

    async def get_leaderboard(self, guild_id: int, start_date: str, end_date: str) -> list:
        docs = await self.wordle_results.find({
            "guild_id": guild_id,
            "season_start": start_date,
            "season_end": end_date,
        }).to_list(length=None)

        users = {}
        for doc in docs:
            user_id = doc["user_id"]
            users.setdefault(user_id, {
                "user_id": user_id,
                "username": doc.get("username", str(user_id)),
                "total_score": 0,
                "games": 0,
                "hard_games": 0,
                "failures": 0,
            })
            users[user_id]["total_score"] += int(doc.get("score", 0))
            users[user_id]["games"] += 1
            users[user_id]["hard_games"] += 1 if doc.get("hard_mode") else 0
            users[user_id]["failures"] += 1 if doc.get("failed") else 0

        return sorted(users.values(), key=lambda row: (row["total_score"], -row["games"], row["username"].lower()))


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
        await self.recurrent.update_one(
            {"channel_id": channel_id},
            {"$pull": {"messages": message}},
        )

    async def update_message_count(self, channel_id: int, message: str, count: int) -> None:
        await self.recurrent.update_one({"channel_id": channel_id}, {"$set": {f"message_counts.{message}": count}})

    async def get_channel_config(self, channel_id: int) -> dict:
        channel_dict = await self.recurrent.find_one({"channel_id": channel_id})
        logging.debug(f"Retrieved channel config: {channel_dict}")
        return channel_dict if channel_dict else {"messages": [], "message_counts": {}, "limit": 0}

    async def add_category_message(self, category_id: int, message: str, limit: int) -> None:
        category_dict = await self.recurrent.find_one({"category_id": category_id})
        if category_dict is None:
            category_dict = {"category_id": category_id, "messages": [message], "message_counts": {message: 0}, "limit": limit}
            await self.recurrent.insert_one(category_dict)
        else:
            if message not in category_dict["messages"]:
                category_dict["messages"].append(message)
                category_dict["message_counts"][message] = 0
            category_dict["limit"] = limit
            await self.recurrent.update_one({"category_id": category_id}, {"$set": {"messages": category_dict["messages"], "message_counts": category_dict["message_counts"], "limit": limit}})

    async def get_category_config(self, category_id: int) -> dict:
        category_dict = await self.recurrent.find_one({"category_id": category_id})
        return category_dict if category_dict else {"messages": [], "message_counts": {}, "limit": 0}

    async def remove_category_message(self, category_id: int, message: str) -> None:
        await self.recurrent.update_one(
            {"category_id": category_id},
            {"$pull": {"messages": message}},
        )
    async def clear_channel_data(self, channel_id: int) -> None:
        await self.recurrent.delete_one({"channel_id": channel_id})

class Database:
    def __init__(self, conf: Config) -> None:
        self.base_db = BaseDatabase(conf)
        self.infraction : InfractionDatabase = InfractionDatabase(self.base_db)
        self.emergency: EmergencyDatabase = EmergencyDatabase()
        self.modmail: ModmailDatabase = ModmailDatabase(conf)
        self.decay = DecayDatabase(conf)
        self.study: StudyDatabase = StudyDatabase()
        self.bonk: BonkDatabase = BonkDatabase()
        self.appeal: AppealDatabase = AppealDatabase()
        self.recurrent: RecurrentDatabase = RecurrentDatabase()
        self.tags: TagsDatabase = TagsDatabase() 
        self.wordle: WordleDatabase = WordleDatabase()
        self.config_lock = asyncio.Lock()
        self.config_data = {} 
