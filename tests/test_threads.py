import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from cogs.threads import (
    QOTD_THREAD_CONFIG_NAME,
    Threads,
    has_qotd_curator_role,
    is_qotd_thread,
)


class FakeThread:
    def __init__(self, thread_id, parent, *, archived=False, created_at=None, owner=None):
        self.id = thread_id
        self.parent = parent
        self.archived = archived
        self.created_at = created_at or datetime(2026, 5, 25, tzinfo=timezone.utc)
        self.owner = owner
        self.edit_calls = []

    async def edit(self, **kwargs):
        self.edit_calls.append(kwargs)
        if "archived" in kwargs:
            self.archived = kwargs["archived"]


class FakeParent:
    def __init__(self, name="qotd"):
        self.name = name
        self.threads = []
        self.archived = []
        self.archived_limits = []

    async def archived_threads(self, limit=50):
        self.archived_limits.append(limit)
        count = 0
        for thread in self.archived:
            if limit is not None and count >= limit:
                break
            count += 1
            yield thread


class FakeBaseDB:
    def __init__(self, config=None):
        self.config = config
        self.updated_config = None

    async def read_bot_config(self, name):
        if name == QOTD_THREAD_CONFIG_NAME:
            return self.config
        return None

    async def update_bot_config(self, config):
        self.config = dict(config)
        self.updated_config = dict(config)


def make_cog(config=None):
    db = SimpleNamespace(base_db=FakeBaseDB(config))
    bot = SimpleNamespace(db=db)
    return Threads(bot), db.base_db


def role(name):
    return SimpleNamespace(name=name)


def test_is_qotd_thread_checks_parent_name():
    qotd_parent = SimpleNamespace(name="qotd")
    other_parent = SimpleNamespace(name="math")

    assert is_qotd_thread(SimpleNamespace(parent=qotd_parent)) is True
    assert is_qotd_thread(SimpleNamespace(parent=other_parent)) is False


def test_has_qotd_curator_role():
    assert has_qotd_curator_role(SimpleNamespace(roles=[role("QOTD Curator")])) is True
    assert has_qotd_curator_role(SimpleNamespace(roles=[role("Student")])) is False


def test_first_qotd_run_closes_all_previous_threads_and_sets_flag():
    cog, db = make_cog(config=None)
    parent = FakeParent()
    curator = SimpleNamespace(roles=[role("QOTD Curator")])

    new_thread = FakeThread(3, parent, owner=curator)
    old_open = FakeThread(1, parent, archived=False)
    old_closed = FakeThread(2, parent, archived=True)
    parent.threads = [new_thread, old_open]
    parent.archived = [old_closed]

    asyncio.run(cog.handle_qotd_thread_create(new_thread))

    assert old_open.archived is True
    assert old_open.edit_calls == [{"archived": True}]
    assert old_closed.edit_calls == []
    assert db.config["initial_check_done"] is True
    assert parent.archived_limits == [None]


def test_later_qotd_runs_only_close_most_recent_previous_thread():
    cog, _ = make_cog(config={"name": QOTD_THREAD_CONFIG_NAME, "initial_check_done": True})
    parent = FakeParent()
    curator = SimpleNamespace(roles=[role("QOTD Curator")])

    older = FakeThread(1, parent, archived=False, created_at=datetime(2026, 5, 20, tzinfo=timezone.utc))
    newest_previous = FakeThread(2, parent, archived=False, created_at=datetime(2026, 5, 24, tzinfo=timezone.utc))
    new_thread = FakeThread(3, parent, owner=curator, created_at=datetime(2026, 5, 25, tzinfo=timezone.utc))
    parent.threads = [older, newest_previous, new_thread]

    asyncio.run(cog.handle_qotd_thread_create(new_thread))

    assert older.archived is False
    assert older.edit_calls == []
    assert newest_previous.archived is True
    assert newest_previous.edit_calls == [{"archived": True}]
    assert parent.archived_limits == []


def test_later_qotd_runs_check_one_archived_thread_when_no_active_previous_thread():
    cog, _ = make_cog(config={"name": QOTD_THREAD_CONFIG_NAME, "initial_check_done": True})
    parent = FakeParent()
    curator = SimpleNamespace(roles=[role("QOTD Curator")])

    new_thread = FakeThread(3, parent, owner=curator)
    archived_previous = FakeThread(2, parent, archived=True)
    parent.threads = [new_thread]
    parent.archived = [archived_previous]

    asyncio.run(cog.handle_qotd_thread_create(new_thread))

    assert archived_previous.edit_calls == []
    assert parent.archived_limits == [1]
