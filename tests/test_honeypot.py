"""Regression tests use an isolated Discord stub; no gateway or DB is contacted."""
import asyncio
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest


@pytest.fixture
def hp(monkeypatch):
    nc, ext, cm, models = map(ModuleType, ("nextcord", "nextcord.ext", "nextcord.ext.commands", "models"))
    class Cog:
        @staticmethod
        def listener():
            return lambda f: f
    class Embed:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs); self.fields = []
        def add_field(self, **kwargs): self.fields.append(kwargs)
        def set_author(self, **kwargs): self.author = kwargs
    class NotFound(Exception): pass
    cm.Cog = Cog; ext.commands = cm; nc.ext = ext
    class File:
        def __init__(self, fp, filename): self.fp=fp; self.filename=filename
        def close(self): self.fp.close()
    nc.File = File
    nc.Embed = Embed; nc.NotFound = NotFound
    nc.MessageType = NS(default=0, reply=19)
    nc.AllowedMentions = NS(none=lambda: None)
    models.Infraction = lambda **kw: NS(**kw)
    for name, module in (("nextcord", nc), ("nextcord.ext", ext), ("nextcord.ext.commands", cm), ("models", models)):
        monkeypatch.setitem(sys.modules, name, module)
    path = Path(__file__).resolve().parents[1] / "src/cogs/honeypot.py"
    spec = importlib.util.spec_from_file_location("honeypot_under_test", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def run(coro): return asyncio.run(coro)


@pytest.fixture
def case(hp, monkeypatch):
    monkeypatch.delenv("APBOT_DATABASE_NAME", raising=False)
    bot_id, guild_id = hp.PRODUCTION_IDENTITY
    hp.HONEYPOT_DRY_RUN = False
    now = datetime.now(timezone.utc)
    role = NS(id=11, name="@everyone", permissions=NS())
    me = NS(id=bot_id, bot=True, roles=[], guild_permissions=NS(ban_members=True), top_role=10)
    author = NS(id=42, bot=False, roles=[], guild_permissions=NS(), top_role=1,
                joined_at=now-timedelta(days=1), send=AsyncMock())
    warning = NS(id=100, author=me, content=hp.ACTIVE_WARNING, webhook_id=None)
    entry = NS(edit=AsyncMock(), jump_url="https://discord.com/channels/1/4/999")
    review = NS(id=4, name="honey-pot-log", overwrites={}, send=AsyncMock(return_value=entry))
    review.permissions_for = lambda target: NS(view_channel=target is me, send_messages=True, embed_links=True, attach_files=True)
    channel = NS(id=3, name="honey-pot", pins=AsyncMock(return_value=[]), send=AsyncMock(return_value=warning))
    channel.notices = [warning]
    async def history(**kw):
        for m in channel.notices: yield m
    channel.history = history
    guild = NS(id=guild_id, owner_id=999, me=me, default_role=role, roles=[role],
               text_channels=[channel, review], fetch_member=AsyncMock(return_value=author), ban=AsyncMock())
    message = NS(id=101, guild=guild, channel=channel, author=author, type=0, webhook_id=None,
                 created_at=now, content="hello", attachments=[], jump_url="https://discord.com/channels/1/3/101", delete=AsyncMock())
    trigger_fetch = AsyncMock(return_value=message)
    warning_fetch = AsyncMock(return_value=warning)
    async def fetch(mid):
        if mid == message.id:
            return await trigger_fetch(mid)
        return await warning_fetch(mid)
    channel.fetch_message = fetch
    db = NS(add_infraction=AsyncMock())
    bot = NS(user=me, intents=NS(message_content=True), config={"guild_id":guild_id,"application_id":bot_id}, get_guild=lambda _:guild, db=NS(base_db=db))
    cog = hp.Honeypot(bot)
    return NS(cog=cog, guild=guild, me=me, author=author, warning=warning, message=message,
              channel=channel, review=review, entry=entry, db=db, bot=bot,
              trigger_fetch=trigger_fetch, warning_fetch=warning_fetch)


def invoke(c): run(c.cog.on_message(c.message))


def test_success(case):
    c=case; invoke(c)
    c.guild.ban.assert_awaited_once_with(c.author, reason="Talking in honeypot", delete_message_seconds=0)
    c.message.delete.assert_awaited_once(); c.db.add_infraction.assert_awaited_once(); c.author.send.assert_awaited_once()
    assert c.entry.edit.call_args.kwargs["embed"].description == "Member banned"
    assert c.db.add_infraction.call_args.args[1].actiontype == "ban"
    assert c.cog.pending == set()


@pytest.mark.parametrize("name", ["Admin", "Moderator", "Chat Moderator", "Lead Moderator", "Trial Chat Moderator", "ADMINISTRATOR", "Trial Moderator"])
def test_staff_names(case, name):
    case.author.roles=[NS(name=name)]; invoke(case); case.guild.ban.assert_not_awaited(); case.review.send.assert_not_awaited()


@pytest.mark.parametrize("perm", ["administrator", "moderate_members", "ban_members", "kick_members", "manage_messages"])
def test_staff_permissions(case, perm):
    setattr(case.author.guild_permissions, perm, True); invoke(case); case.guild.ban.assert_not_awaited()


def test_exact_name(case):
    case.author.roles=[NS(name="Moderator Club")]; invoke(case); case.guild.ban.assert_awaited_once()


@pytest.mark.parametrize("condition", ["bot", "owner", "webhook", "system", "wrong_guild", "wrong_bot", "wrong_config", "wrong_channel", "duplicate_channel", "old_message", "disabled", "dm"])
def test_not_eligible(hp, case, condition):
    c=case
    if condition=="bot": c.author.bot=True
    elif condition=="owner": c.guild.owner_id=c.author.id
    elif condition=="webhook": c.message.webhook_id=10
    elif condition=="system": c.message.type=6
    elif condition=="wrong_guild": c.guild.id=123
    elif condition=="wrong_bot": c.bot.user.id=123
    elif condition=="wrong_config": c.bot.config["application_id"]=123
    elif condition=="wrong_channel": c.message.channel=NS(id=8,name="general")
    elif condition=="duplicate_channel": c.guild.text_channels.append(NS(id=8,name="honey-pot"))
    elif condition=="old_message": c.message.created_at-=timedelta(minutes=5)
    elif condition=="disabled": hp.HONEYPOT_ENABLED=False
    elif condition=="dm": c.message.guild=None
    invoke(c); c.guild.ban.assert_not_awaited(); c.review.send.assert_not_awaited()


@pytest.mark.parametrize("kind", ["missing", "foreign", "wrong_text", "late"])
def test_warning_required(case, kind):
    c=case
    if kind=="missing": c.channel.notices=[]
    elif kind=="foreign": c.warning.author=c.author
    elif kind=="wrong_text": c.warning.content="warning"
    else: c.warning.id=102
    invoke(c); c.guild.ban.assert_not_awaited(); c.review.send.assert_not_awaited()


@pytest.mark.parametrize("test_identity", [False, True])
def test_dry_run(hp, case, test_identity, monkeypatch):
    c=case
    if test_identity:
        c.bot.user.id,c.guild.id=hp.TEST_IDENTITY
        c.bot.config={"guild_id":c.guild.id,"application_id":c.bot.user.id}
        monkeypatch.setenv("APBOT_DATABASE_NAME", "ap-test")
    hp.HONEYPOT_DRY_RUN=True
    c.warning.content=hp.DRY_WARNING; invoke(c)
    c.review.send.assert_awaited_once(); c.guild.ban.assert_not_awaited(); c.message.delete.assert_not_awaited(); c.db.add_infraction.assert_not_awaited(); c.author.send.assert_not_awaited()


@pytest.mark.parametrize("problem", ["everyone", "ordinary_role", "unknown_member", "missing_perms", "missing_log", "duplicate_log", "send_fail"])
def test_private_log(case, problem):
    c=case
    if problem=="everyone": c.review.permissions_for=lambda _:NS(view_channel=True)
    elif problem=="ordinary_role":
        r=NS(id=555,name="Members",permissions=NS()); c.guild.roles.append(r)
        c.review.permissions_for=lambda t:NS(view_channel=t is r or t is c.me,send_messages=True,embed_links=True,attach_files=True)
    elif problem=="unknown_member":
        class Target: id=555
        c.review.overwrites={Target():NS(view_channel=True)}
    elif problem=="missing_perms": c.review.permissions_for=lambda t:NS(view_channel=t is c.me,send_messages=True,embed_links=False)
    elif problem=="missing_log": c.guild.text_channels.remove(c.review)
    elif problem=="duplicate_log": c.guild.text_channels.append(NS(id=7,name="honey-pot-log"))
    elif problem=="send_fail": c.review.send.side_effect=RuntimeError("send failed")
    invoke(c); c.guild.ban.assert_not_awaited()


@pytest.mark.parametrize("name",["Bot Staff","Senior Bot Staff","Chat Moderator"])
def test_log_access(case, name):
    c=case; r=NS(id=555,name=name,permissions=NS()); c.guild.roles.append(r)
    c.review.permissions_for=lambda t:NS(view_channel=t is r or t is c.me,send_messages=True,embed_links=True,attach_files=True)
    invoke(c); c.guild.ban.assert_awaited_once()


@pytest.mark.parametrize("problem",["hierarchy","no_ban_permission","left","fetch_failure","rejoined","promoted","notice_deleted","log_now_public"])
def test_revalidation(hp, case, problem):
    c=case
    if problem=="hierarchy": c.author.top_role=10
    elif problem=="no_ban_permission": c.me.guild_permissions.ban_members=False
    elif problem=="left": c.guild.fetch_member.side_effect=hp.nextcord.NotFound()
    elif problem=="fetch_failure": c.trigger_fetch.side_effect=RuntimeError("fetch failed")
    elif problem=="rejoined": c.author.joined_at=c.message.created_at+timedelta(seconds=1)
    elif problem=="promoted":
        c.guild.fetch_member.side_effect=[c.author,NS(id=c.author.id,roles=[NS(name="Moderator")],guild_permissions=NS())]
    elif problem=="notice_deleted":
        async def gone(mid):
            c.channel.notices=[]
            raise hp.nextcord.NotFound()
        c.warning_fetch.side_effect=gone
    elif problem=="log_now_public":
        async def send(**kw):
            c.review.permissions_for=lambda _:NS(view_channel=True); return c.entry
        c.review.send.side_effect=send
    invoke(c); c.guild.ban.assert_not_awaited(); c.message.delete.assert_not_awaited()


def test_ban_failure(case):
    case.guild.ban.side_effect=RuntimeError("failure"); invoke(case)
    case.db.add_infraction.assert_not_awaited(); case.message.delete.assert_not_awaited(); case.author.send.assert_not_awaited()
    assert case.entry.edit.call_args.kwargs["embed"].description=="Ban failed or unconfirmed"


def test_database_failure(case, caplog):
    case.db.add_infraction.side_effect=RuntimeError("failure"); invoke(case)
    case.guild.ban.assert_awaited_once(); case.message.delete.assert_awaited_once()
    assert "write failed" in caplog.text


def test_pending(case):
    c=case
    async def burst(): await asyncio.gather(*(c.cog.on_message(c.message) for _ in range(10)))
    run(burst()); c.guild.ban.assert_awaited_once()


def test_overload(case):
    c=case; c.cog.pending={(c.guild.id,i) for i in range(4)}; invoke(c); c.guild.ban.assert_not_awaited()


def test_notice_already_present_unpinned(case):
    run(case.cog.on_ready()); case.channel.send.assert_not_awaited()


def test_notice_created(case):
    c=case; c.channel.notices=[]
    async def history(**kw):
        if False: yield None
    c.channel.history=history
    run(c.cog.on_ready()); c.channel.send.assert_awaited_once(); assert c.channel.send.call_args.args[0].startswith("# ⚠️ WARNING")


def test_active_default(hp):
    assert hp.HONEYPOT_DRY_RUN is False
    assert "up to two weeks" in hp.ACTIVE_WARNING.lower()
    assert "Unbanning is not guaranteed" not in hp.ACTIVE_WARNING
    assert "are exempt" not in hp.ACTIVE_WARNING
    assert hp.APPEAL_URL not in hp.ACTIVE_WARNING

@pytest.mark.parametrize("db_name", [None, "ap-students", "ap-test"])
def test_test_identity_enforcement(hp, case, monkeypatch, db_name):
    c=case
    c.bot.user.id,c.guild.id=hp.TEST_IDENTITY
    c.bot.config={"guild_id":c.guild.id,"application_id":c.bot.user.id}
    if db_name is None: monkeypatch.delenv("APBOT_DATABASE_NAME", raising=False)
    else: monkeypatch.setenv("APBOT_DATABASE_NAME", db_name)
    invoke(c)
    if db_name == "ap-test": c.guild.ban.assert_awaited_once()
    else: c.guild.ban.assert_not_awaited(); c.review.send.assert_not_awaited()

def test_production_refuses_test_db(case, monkeypatch):
    monkeypatch.setenv("APBOT_DATABASE_NAME", "ap-test")
    invoke(case); case.guild.ban.assert_not_awaited()

@pytest.mark.parametrize("when", ["first", "second", "both"])
def test_deleted_trigger_still_counts(hp, case, when, caplog):
    c=case
    gone=hp.nextcord.NotFound()
    c.trigger_fetch.side_effect={"first":[gone,c.message], "second":[c.message,gone], "both":[gone,gone]}[when]
    c.message.delete.side_effect=hp.nextcord.NotFound()
    invoke(c); c.guild.ban.assert_awaited_once()
    assert "already gone" in caplog.text

def test_log_fields(case):
    case.message.content="hello `world`"
    case.message.attachments=[attachment(),attachment()]
    invoke(case)
    embed=case.entry.edit.call_args.kwargs["embed"]
    fields={f["name"]:f["value"] for f in embed.fields}
    assert fields["Attachments"]=="2"
    assert "hello ˋworldˋ" in fields["Text"]
    assert fields["Message ID"] == "`101`"
    assert not {"Message", "Reason", "Result"}.intersection(fields)
    assert "Jump to message" not in str(embed.fields)
    assert embed.timestamp is not None



def attachment(data=b"image data", filename="example.png"):
    return NS(size=len(data), filename=filename, read=AsyncMock(return_value=data))


def test_evidence_above_embed(case):
    c=case; c.message.attachments=[attachment(b"a"),attachment(b"b", "file.pdf")]
    events=[]
    async def send(**kw):
        if "file" in kw:
            f=kw["file"]; events.append(("file", f.filename, f.fp.read()))
        else: events.append(("embed", kw["embed"].description))
        return c.entry
    async def ban(*args, **kw): events.append(("ban",))
    c.review.send.side_effect=send; c.guild.ban.side_effect=ban
    invoke(c)
    assert [x[0] for x in events]==["file","file","embed","ban"]
    assert events[0][2]==b"a" and events[1][2]==b"b"
    assert "Evidence" in str(c.entry.edit.call_args.kwargs["embed"].fields)

@pytest.mark.parametrize("problem",["too_big","missing_attach_files","read_failure","upload_failure","size_mismatch","too_many","total_limit"])
def test_evidence_fail_closed(hp, case, problem):
    c=case; a=attachment(); c.message.attachments=[a]
    if problem=="too_big": a.size=hp.MAX_ATTACHMENT_BYTES+1
    elif problem=="missing_attach_files": c.review.permissions_for=lambda t:NS(view_channel=t is c.me,send_messages=True,embed_links=True,attach_files=False)
    elif problem=="read_failure": a.read.side_effect=RuntimeError("read failed")
    elif problem=="upload_failure": c.review.send.side_effect=RuntimeError("upload failed")
    elif problem=="size_mismatch": a.size+=1
    elif problem=="too_many": c.message.attachments=[a]*11
    elif problem=="total_limit": a.size=hp.MAX_ATTACHMENT_BYTES; c.message.attachments=[a]*4
    invoke(c); c.guild.ban.assert_not_awaited(); c.message.delete.assert_not_awaited()


def test_original_message_preserved_after_edit(case):
    c=case; c.message.content="original "*200; a=attachment(); c.message.attachments=[a]
    async def fetch(*args):
        c.message.content="edited"; c.message.attachments=[]; return c.message
    c.trigger_fetch.side_effect=fetch
    sent=[]
    async def send(**kw):
        if "file" in kw: sent.append(kw["file"].fp.read())
        return c.entry
    c.review.send.side_effect=send
    invoke(c); c.guild.ban.assert_awaited_once()
    assert sent==[b"original "*200,b"image data"]
    assert "original" in str(c.entry.edit.call_args.kwargs["embed"].fields)


def test_cache_fallback(hp, case):
    a=attachment(); a.read.side_effect=[hp.nextcord.NotFound(),b"image data"]
    case.message.attachments=[a]; invoke(case)
    a.read.assert_awaited_with(use_cached=True); case.guild.ban.assert_awaited_once()


def test_sticker_metadata(case):
    c=case; c.message.stickers=[NS(id=123,name="Sticker")]; sent=[]
    async def send(**kw):
        if "file" in kw: sent.append(kw["file"].fp.read())
        return c.entry
    c.review.send.side_effect=send; invoke(c)
    assert b'Sticker' in sent[0]; c.guild.ban.assert_awaited_once()


def test_evidence_timeout(hp,case,monkeypatch):
    a=attachment(); case.message.attachments=[a]
    async def slow(**kw): await asyncio.sleep(1)
    a.read.side_effect=slow; monkeypatch.setattr(hp,"EVIDENCE_TIMEOUT",0.001)
    invoke(case); case.guild.ban.assert_not_awaited()


def test_missing_message_content_intent(case):
    case.bot.intents.message_content=False; invoke(case); case.guild.ban.assert_not_awaited()


def test_unpinned_warning_enforces(case):
    c=case; invoke(c)
    c.guild.ban.assert_awaited_once()
    c.channel.pins.assert_not_awaited()


def test_cached_notice_survives_history_window(case):
    c=case; run(c.cog.on_ready()); c.channel.notices=[]
    invoke(c); c.guild.ban.assert_awaited_once()


def test_cached_warning_changed(case):
    c=case; run(c.cog.on_ready()); c.warning.content="changed"
    invoke(c); c.guild.ban.assert_not_awaited()


def test_warning_fetch_failure(case):
    c=case; run(c.cog.on_ready()); c.warning_fetch.side_effect=RuntimeError("REST failure")
    invoke(c); c.guild.ban.assert_not_awaited()


def test_ban_dm_matches_manual_style(hp, case):
    case.author.display_name = "Example"
    case.author.display_avatar = NS(url="https://example.invalid/avatar.png")
    case.bot.colors = {"red": 12345}
    invoke(case)
    infraction = case.db.add_infraction.call_args.args[1]
    dm = case.author.send.call_args.kwargs["embed"]
    assert not case.author.send.call_args.args
    assert dm.title == "Infraction: Ban"
    assert dm.description == "**Reason:**\nTalking in honeypot"
    assert dm.color == 12345 and dm.timestamp == infraction.actiontime
    assert dm.author == {"name": "Example", "icon_url": "https://example.invalid/avatar.png"}
    assert dm.fields == [{"name": "Appeal", "value": "If you wish to appeal your ban, you may do so by joining the following server: " + hp.APPEAL_URL, "inline": False}]
    assert infraction.reason == hp.BAN_REASON


def test_evidence_upload_has_no_caption(case):
    case.message.attachments = [attachment()]
    invoke(case)
    upload = case.review.send.call_args_list[0].kwargs
    assert "file" in upload and "content" not in upload
    assert "101" in upload["file"].filename


def test_dm_failure_still_logged(case, caplog):
    case.author.send.side_effect = RuntimeError("DM blocked")
    invoke(case)
    case.guild.ban.assert_awaited_once()
    assert "DM failed or unconfirmed" in caplog.text
    assert "Result" not in {f["name"] for f in case.entry.edit.call_args.kwargs["embed"].fields}
