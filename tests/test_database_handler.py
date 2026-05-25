import asyncio
import copy
from datetime import datetime, timezone
from types import SimpleNamespace

from database_handler import BaseDatabase
from models import Infraction


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = [copy.deepcopy(doc) for doc in (docs or [])]

    def _matches(self, doc, query):
        return all(doc.get(key) == value for key, value in query.items())

    async def find_one(self, query):
        for doc in self.docs:
            if self._matches(doc, query):
                return copy.deepcopy(doc)
        return None

    async def insert_one(self, doc):
        stored = copy.deepcopy(doc)
        stored.setdefault("_id", len(self.docs) + 1)
        self.docs.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    async def replace_one(self, query, new_doc, upsert=False):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                stored = copy.deepcopy(new_doc)
                stored.setdefault("_id", doc.get("_id"))
                self.docs[index] = stored
                return SimpleNamespace(modified_count=1)

        if upsert:
            stored = copy.deepcopy(new_doc)
            stored.setdefault("_id", len(self.docs) + 1)
            self.docs.append(stored)
            return SimpleNamespace(modified_count=1)

        return SimpleNamespace(modified_count=0)


def make_base_db(user_docs=None):
    db = object.__new__(BaseDatabase)
    db.user_config = FakeCollection(user_docs)
    db.bot_config = FakeCollection()
    db.database = {"channel_config": FakeCollection()}
    return db


def test_read_user_config_creates_default_document_when_missing():
    db = make_base_db()

    result = asyncio.run(db.read_user_config(123))

    assert result["user_id"] == 123
    assert result["infraction_points"] == 0
    assert result["infractions"] == []
    assert len(db.user_config.docs) == 1


def test_add_inf_points_updates_existing_total():
    db = make_base_db()
    saved = {}

    async def fake_read(user_id):
        return {"user_id": user_id, "infraction_points": 7}

    async def fake_update(user_id, new_config):
        saved["user_id"] = user_id
        saved["config"] = copy.deepcopy(new_config)

    db.read_user_config = fake_read
    db.update_user_config = fake_update

    result = asyncio.run(db.add_inf_points(321, 5))

    assert result == 12
    assert saved["user_id"] == 321
    assert saved["config"]["infraction_points"] == 12


def test_add_infraction_round_trip_normalizes_storage_and_points():
    db = make_base_db()
    infraction = Infraction(
        actiontype="mute",
        reason="Repeated spam",
        moderator=SimpleNamespace(id=999),
        actiontime=datetime(2024, 1, 1, 12, 0, 0),
        duration=6 * 3600,
        attachment_url="https://example.com/evidence.png",
    )

    asyncio.run(db.add_infraction(42, infraction))
    stored_config = asyncio.run(db.read_user_config(42))
    stored_infraction = stored_config["infractions"][0]
    restored = asyncio.run(db.get_user_infractions(42))

    assert stored_infraction["moderator"] == 999
    assert stored_infraction["actiontime"].endswith("+00:00")
    assert stored_config["infraction_points"] == 10
    assert len(restored) == 1
    assert restored[0].actiontype == "mute"
    assert restored[0].reason == "Repeated spam"
    assert restored[0].actiontime.tzinfo == timezone.utc


def test_get_user_infractions_normalizes_basic_legacy_records():
    db = make_base_db(
        [
            {
                "_id": 1,
                "user_id": 5,
                "infraction_points": 0,
                "infractions": [
                    {
                        "type": "warn",
                        "actiontime": "2024-02-03T10:15:00",
                    }
                ],
            }
        ]
    )

    infractions = asyncio.run(db.get_user_infractions(5))

    assert len(infractions) == 1
    assert infractions[0].actiontype == "warn"
    assert infractions[0].reason == "No reason provided"
    assert infractions[0].moderator == 0
    assert infractions[0].actiontime == datetime(2024, 2, 3, 10, 15, 0, tzinfo=timezone.utc)


def test_get_user_infractions_normalizes_old_mute_records():
    db = make_base_db(
        [
            {
                "_id": 1,
                "user_id": 5,
                "infraction_points": 0,
                "infractions": [
                    {
                        "type": "mute",
                        "mute_reason": "Old spam reason",
                        "mute_moderator": "<@999999999999999999>",
                        "date": datetime(2024, 2, 3, 10, 15, 0),
                        "duration": 1800,
                        "attachment": "https://example.com/old.png",
                    }
                ],
            }
        ]
    )

    infractions = asyncio.run(db.get_user_infractions(5))

    assert len(infractions) == 1
    assert infractions[0].actiontype == "mute"
    assert infractions[0].reason == "Old spam reason"
    assert infractions[0].moderator == 999999999999999999
    assert infractions[0].duration == 1800
    assert infractions[0].attachment_url == "https://example.com/old.png"
    assert infractions[0].actiontime == datetime(2024, 2, 3, 10, 15, 0, tzinfo=timezone.utc)