import asyncio
import copy
from types import SimpleNamespace

from cogs.tags import can_upload_tag_image, is_image_attachment, normalize_tag_name
from database_handler import TagsDatabase


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, length=None):
        return copy.deepcopy(self.docs)


class FakeCollection:
    def __init__(self):
        self.docs = []

    def matches(self, doc, query):
        return all(doc.get(key) == value for key, value in query.items())

    async def find_one(self, query):
        for doc in self.docs:
            if self.matches(doc, query):
                return copy.deepcopy(doc)
        return None

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    async def delete_one(self, query):
        self.docs = [doc for doc in self.docs if not self.matches(doc, query)]

    async def update_one(self, query, update):
        for doc in self.docs:
            if self.matches(doc, query):
                doc.update(update.get("$set", {}))
                return

    def find(self, query):
        return FakeCursor([doc for doc in self.docs if self.matches(doc, query)])

    async def delete_many(self, query):
        self.docs = [doc for doc in self.docs if not self.matches(doc, query)]


def make_tags_db():
    db = object.__new__(TagsDatabase)
    db.tags = FakeCollection()
    return db


def test_normalize_tag_name():
    assert normalize_tag_name("  Unit   Circle  ") == "unit circle"


def test_can_upload_tag_image_requires_honorable():
    member = SimpleNamespace(roles=[SimpleNamespace(name="Honorable")])
    other = SimpleNamespace(roles=[SimpleNamespace(name="Student")])

    assert can_upload_tag_image(member) is True
    assert can_upload_tag_image(other) is False


def test_is_image_attachment_checks_content_type_or_extension():
    assert is_image_attachment(SimpleNamespace(content_type="image/png", filename="file.bin")) is True
    assert is_image_attachment(SimpleNamespace(content_type=None, filename="graph.PNG")) is True
    assert is_image_attachment(SimpleNamespace(content_type="text/plain", filename="notes.txt")) is False


def test_tags_database_keeps_user_tags_private():
    db = make_tags_db()

    asyncio.run(db.create(1, 10, "z tag", "second", None))
    asyncio.run(db.create(1, 10, "unit circle", "mine", None))
    asyncio.run(db.create(1, 20, "unit circle", "theirs", "https://example.com/a.png"))

    my_tag = asyncio.run(db.get_tag(1, 10, "unit circle"))
    their_tag = asyncio.run(db.get_tag(1, 20, "unit circle"))
    my_tags = asyncio.run(db.get_all(1, 10))

    assert my_tag["content"] == "mine"
    assert their_tag["content"] == "theirs"
    assert [tag["name"] for tag in my_tags] == ["unit circle", "z tag"]
    assert my_tags[0]["user_id"] == 10

    asyncio.run(db.delete(1, 10, "unit circle"))

    assert asyncio.run(db.get_tag(1, 10, "unit circle")) is None
    assert asyncio.run(db.get_tag(1, 20, "unit circle")) is not None


def test_tags_database_blocks_duplicate_names_for_same_user():
    db = make_tags_db()

    asyncio.run(db.create(1, 10, "unit circle", "mine", None))

    try:
        asyncio.run(db.create(1, 10, "unit circle", "duplicate", None))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected duplicate tag creation to fail")

    tags = asyncio.run(db.get_all(1, 10))
    assert len(tags) == 1
    assert tags[0]["content"] == "mine"


def test_tags_database_update_is_user_scoped():
    db = make_tags_db()

    asyncio.run(db.create(1, 10, "unit circle", "mine", None))
    asyncio.run(db.create(1, 20, "unit circle", "theirs", None))

    asyncio.run(db.update(1, 10, "unit circle", "updated", "https://example.com/new.png"))

    my_tag = asyncio.run(db.get_tag(1, 10, "unit circle"))
    their_tag = asyncio.run(db.get_tag(1, 20, "unit circle"))

    assert my_tag["content"] == "updated"
    assert my_tag["image_url"] == "https://example.com/new.png"
    assert their_tag["content"] == "theirs"
