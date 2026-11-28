"""Review-only testing: staff may submit evidence, nobody is punished."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from test_scam_image_detector import harness, BEAST, TRUMP
from cogs import scam_image_detector as cog

@pytest.fixture
def test_harness(harness):
    d,m,s,r,j=harness
    d.bot.user.id=cog.TEST_BOT_ID
    d.bot.config.update(application_id=cog.TEST_BOT_ID, guild_id=cog.TEST_GUILD_ID,
                        scam_detector_test_mode=True, scam_detector_dry_run=False)
    m.guild.id=cog.TEST_GUILD_ID
    m.guild.me.id=cog.TEST_BOT_ID
    m.author.guild_permissions.administrator=True
    m.author.timeout=AsyncMock(); m.guild.ban=AsyncMock()
    r.permissions_for=lambda who:NS(view_channel=who is m.guild.me,send_messages=True,embed_links=True,attach_files=True)
    return d,m,s,r,cog.Job(cog.TEST_GUILD_ID,2,7,0)

def test_admin_flag_no_action_even_when_dry_run_false(test_harness):
    d,m,s,r,j=test_harness
    assert d.eligible(m)
    async def send(**kw):
        if 'files' in kw:
            assert 'embed' not in kw
            assert kw['files'][0].fp.read()==b'scamdata'
            assert not kw['files'][0].filename.startswith('SPOILER_')
        else:
            assert 'files' not in kw
            assert not getattr(getattr(kw['embed'], 'image', None), 'url', None)
            assert kw['embed'].description=='Test mode: no action taken.'
    r.send.side_effect=send
    asyncio.run(d.process(j))
    assert r.send.await_count==2; m.delete.assert_not_called(); m.author.timeout.assert_not_called(); m.guild.ban.assert_not_called()

@pytest.mark.parametrize('wrong', ['bot','guild'])
def test_test_mode_cannot_run_elsewhere(test_harness,wrong):
    d,m,s,r,j=test_harness
    if wrong=='bot': d.bot.user.id=99; d.bot.config['application_id']=99
    else: m.guild.id=1; d.bot.config['guild_id']=1; j=cog.Job(1,2,7,0)
    asyncio.run(d.process(j)); assert not d.eligible(m); r.send.assert_not_called(); m.delete.assert_not_called()

def test_multi_image_only_matching_ones(test_harness):
    d,m,s,r,j=test_harness
    m.attachments=[NS(id=i,filename='a.png',size=1,content_type='image/png',read=AsyncMock(return_value=bytes([i]))) for i in range(3)]
    d.ocr.scan.side_effect=[BEAST,'AP Biology',TRUMP]
    captured=[]
    async def send(**kw): captured.extend(f.fp.read() for f in kw.get('files', []))
    r.send.side_effect=send
    asyncio.run(d.process(j)); assert captured==[b'\x00',b'\x02']; assert r.send.await_count==2; m.delete.assert_not_called(); m.author.timeout.assert_not_called()

def test_spam_repeated_matches_logged_cached(test_harness):
    d,m,s,r,j=test_harness
    async def run():
        for i in range(5):
            m.id=7+i
            await d.process(cog.Job(j.guild_id,j.channel_id,m.id,0))
    asyncio.run(run()); assert r.send.await_count==10; d.ocr.scan.assert_awaited_once(); m.delete.assert_not_called(); m.author.timeout.assert_not_called()

@pytest.mark.parametrize('kind',['text','clean','no_attach_permission','public_log'])
def test_test_mode_does_not_log_unrelated_or_unsafe(test_harness,kind):
    d,m,s,r,j=test_harness
    if kind=='text': m.attachments=[]; m.content=BEAST
    elif kind=='clean': d.ocr.scan.return_value='AP Biology'
    elif kind=='no_attach_permission': r.permissions_for=lambda who:NS(view_channel=who is m.guild.me,send_messages=True,embed_links=True,attach_files=False)
    else: r.permissions_for=lambda who:NS(view_channel=True,send_messages=True,embed_links=True,attach_files=True)
    asyncio.run(d.process(j)); r.send.assert_not_called(); m.delete.assert_not_called(); m.author.timeout.assert_not_called()


def test_admin_listener_queues_image(test_harness):
    d,m,s,r,j=test_harness
    async def run():
        await d.on_message(m)
        await asyncio.wait_for(d.queue.join(), 2)
        d.cog_unload()
        await asyncio.gather(d.task,return_exceptions=True)
    asyncio.run(run()); assert r.send.await_count==2; m.delete.assert_not_called(); m.author.timeout.assert_not_called()
