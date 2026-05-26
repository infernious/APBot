import asyncio
import copy
from datetime import datetime, timezone
from types import SimpleNamespace

from database_handler import BaseDatabase, WordleDatabase
from models import Infraction


class FakeCursor:
    def __init__(self, docs):
        self.docs = [copy.deepcopy(doc) for doc in docs]

    async def to_list(self, length=None):
        return copy.deepcopy(self.docs)


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

    async def update_one(self, query, update, upsert=False):
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                stored = copy.deepcopy(doc)
                stored.update(copy.deepcopy(update.get("$set", {})))
                self.docs[index] = stored
                return SimpleNamespace(modified_count=1, upserted_id=None)

        if upsert:
            stored = copy.deepcopy(query)
            stored.update(copy.deepcopy(update.get("$set", {})))
            stored.setdefault("_id", len(self.docs) + 1)
            self.docs.append(stored)
            return SimpleNamespace(modified_count=0, upserted_id=stored["_id"])

        return SimpleNamespace(modified_count=0, upserted_id=None)

    async def update_many(self, query, update):
        modified_count = 0

        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                stored = copy.deepcopy(doc)
                stored.update(copy.deepcopy(update.get("$set", {})))
                self.docs[index] = stored
                modified_count += 1

        return SimpleNamespace(modified_count=modified_count)

    def find(self, query):
        return FakeCursor([doc for doc in self.docs if self._matches(doc, query)])


def make_base_db(user_docs=None):
    db = object.__new__(BaseDatabase)
    db.user_config = FakeCollection(user_docs)
    db.bot_config = FakeCollection()
    db.database = {"channel_config": FakeCollection()}
    return db


def make_wordle_db(season_docs=None, result_docs=None):
    db = object.__new__(WordleDatabase)
    db.wordle_seasons = FakeCollection(season_docs)
    db.wordle_results = FakeCollection(result_docs)
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


def test_get_user_infractions_recovers_legacy_moderator_id_with_extra_digits():
    db = make_base_db(
        [
            {
                "_id": 1,
                "user_id": 5,
                "infraction_points": 0,
                "infractions": [
                    {
                        "type": "warn",
                        "mute_moderator": "7079852600207606280",
                        "date": datetime(2024, 2, 3, 10, 15, 0),
                    }
                ],
            }
        ]
    )

    infractions = asyncio.run(db.get_user_infractions(5))

    assert infractions[0].moderator == 707985260020760628


def test_update_infraction_reason_updates_new_and_legacy_reason_fields():
    db = make_base_db([
        {
            "_id": 1,
            "user_id": 5,
            "infraction_points": 0,
            "infractions": [{"type": "mute", "mute_reason": "old"}],
        }
    ])

    result = asyncio.run(db.update_infraction_reason(5, 1, "new reason"))
    stored = asyncio.run(db.read_user_config(5))

    assert result is True
    assert stored["infractions"][0]["reason"] == "new reason"
    assert stored["infractions"][0]["mute_reason"] == "new reason"


def test_add_infraction_note_appends_update_entry():
    db = make_base_db([
        {
            "_id": 1,
            "user_id": 5,
            "infraction_points": 0,
            "infractions": [{"actiontype": "warn", "reason": "old"}],
        }
    ])
    date = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    result = asyncio.run(db.add_infraction_note(5, 1, 999, "extra context", date))
    stored = asyncio.run(db.read_user_config(5))

    assert result is True
    assert stored["infractions"][0]["update"][0]["moderator"] == 999
    assert stored["infractions"][0]["update"][0]["update"] == "extra context"
    assert stored["infractions"][0]["update"][0]["date"] == "2024-01-02T03:04:05+00:00"


def test_delete_infraction_removes_only_selected_index():
    db = make_base_db([
        {
            "_id": 1,
            "user_id": 5,
            "infraction_points": 10,
            "infractions": [
                {"actiontype": "warn", "reason": "first"},
                {"actiontype": "mute", "reason": "second"},
            ],
        }
    ])

    result = asyncio.run(db.delete_infraction(5, 1))
    stored = asyncio.run(db.read_user_config(5))

    assert result is True
    assert len(stored["infractions"]) == 1
    assert stored["infractions"][0]["reason"] == "second"
    assert stored["infraction_points"] == 10


def test_infraction_update_helpers_reject_bad_index():
    db = make_base_db([
        {"_id": 1, "user_id": 5, "infraction_points": 0, "infractions": []}
    ])

    assert asyncio.run(db.update_infraction_reason(5, 1, "reason")) is False
    assert asyncio.run(db.add_infraction_note(5, 1, 999, "note")) is False
    assert asyncio.run(db.delete_infraction(5, 1)) is False
