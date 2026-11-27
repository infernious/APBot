import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from test_welcome_v2 import cog_module, fake_cog, fake_message, fake_log_guild
from test_welcome import FakeStore, FakeTransport
from utils.welcome_store import StickyReminder
from utils.welcome_validator import classify, Decision

@pytest.mark.parametrize('text', ["I'm Alex :)", "im alex johnson", "you can call me sam", "junior here", "currently in ap chem", "I do robotics", "I'm Alex (he/him)", "I wanna be a surgeon", "from India", "1. Name: Alex\n2. Grade: 11", "||I'm Alex||", "Ahmed here", "I'm in band", "need help with ap chem", "# Hi I'm Alex", "I graduate in 2027"])
def test_valid_or_review(text):
    assert classify(text).decision != Decision.REJECT

@pytest.mark.parametrize('text', ['dsc.gg/abc', 'discord.me/abc', 'invite.gg/abc', 'discord.gift/abc', 'discord.new/abc', 'buy followers cheap at example.com', 'free nitro at https://x.co'])
def test_spam_after_intro(text):
    assert classify("I'm a junior taking AP Bio.\n" + text).decision == Decision.REJECT

@pytest.mark.parametrize('text', ['digger', 'Alex', 'student loan', 'new here', 'random text'])
def test_uncertain_retained_and_flagged(cog_module,text):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,text)
        await c.on_message(m)
        assert not m.delete.called and c.dm_queue.empty()
        entry=c.log_queue.get_nowait()
        assert entry[4]=='no_introduction_evidence' and entry[5]==''
        assert c.schedule.called
    asyncio.run(run())

def test_uncertain_dry_run_no_channel_log(cog_module):
    async def run():
        c=fake_cog(cog_module,dry=True); m=fake_message(cog_module,'new here')
        await c.on_message(m)
        assert not m.delete.called and c.dm_queue.empty() and c.log_queue.empty()
        assert c.counters['no_introduction_evidence']==1
    asyncio.run(run())

def test_correction_before_delete(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'hi')
        cog_module.DELETE_GRACE_SECONDS=.15
        fixed=fake_message(cog_module,"I'm a junior taking AP Bio")
        m.channel.fetch_message.return_value=fixed
        c.bot.get_guild=lambda _: NS(id=1)
        t=asyncio.create_task(c.on_message(m)); await asyncio.sleep(.03)
        await c.on_raw_message_edit(NS(data={'content':fixed.content},guild_id=1,channel_id=2,message_id=m.id))
        await t
        assert not m.delete.called and not fixed.delete.called
        assert c.dm_queue.empty() and c.log_queue.empty() and not c.pending and not c.edited
    asyncio.run(run())

def test_edit_during_fetch_fails_open(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'hi'); started=asyncio.Event(); release=asyncio.Event()
        async def fetch(_):
            started.set(); await release.wait(); return m
        m.channel.fetch_message=fetch; c.bot.get_guild=lambda _:NS(id=1)
        task=asyncio.create_task(c.on_message(m)); await started.wait()
        await c.on_raw_message_edit(NS(data={'content':"I'm Alex"},guild_id=1,channel_id=2,message_id=m.id)); release.set(); await task
        assert not m.delete.called and c.counters['edit_during_fetch']==1
    asyncio.run(run())

def test_fetch_failure_never_deletes(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'hi'); m.channel.fetch_message.side_effect=cog_module.nextcord.Forbidden()
        await c.on_message(m)
        assert not m.delete.called and c.dm_queue.empty() and c.log_queue.empty()
    asyncio.run(run())

def test_log_rejects_nonstaff_role(cog_module):
    c=fake_cog(cog_module); guild,ch=fake_log_guild(c)
    guild.roles=[guild.default_role,NS(permissions=NS(manage_messages=False,administrator=False))]
    assert c.log_channel(guild) is None

def test_log_rejects_member_overwrite(cog_module):
    c=fake_cog(cog_module); guild,ch=fake_log_guild(c)
    ch.overwrites={object():NS(view_channel=True)}
    assert c.log_channel(guild) is None

def test_mongo_outage_repeated_traffic():
    async def run():
        s=FakeStore(); t=FakeTransport(); r=StickyReminder(s,t,1,2); await r.refresh(); s.fail=True
        for _ in range(12):
            t.post_ordinary()
            with pytest.raises(RuntimeError): await r.refresh(ensure=True,recovered=list(t.messages))
            assert len(t.messages)==1
        s.fail=False; await r.refresh(ensure=True,recovered=list(t.messages)); assert len(t.messages)==1
    asyncio.run(run())

def test_uncached_member_edit_revalidated(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'discord.gg/abc'); member=m.author
        m.author=NS(id=member.id,bot=False); m.guild.get_member=lambda _:member
        c.bot.get_guild=lambda _: NS(id=1,get_channel=lambda _:m.channel)
        await c.on_raw_message_edit(NS(data={'content':m.content},guild_id=1,channel_id=2,message_id=m.id))
        assert m.delete.await_count==1
    asyncio.run(run())

def test_uncached_staff_edit_exempt(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'hi',staff=True); member=m.author
        m.author=NS(id=member.id,bot=False); m.guild.get_member=lambda _:member
        c.bot.get_guild=lambda _: NS(id=1,get_channel=lambda _:m.channel)
        await c.on_raw_message_edit(NS(data={'content':m.content},guild_id=1,channel_id=2,message_id=m.id))
        assert not m.delete.called
    asyncio.run(run())

def test_edit_overload_counted(cog_module):
    async def run():
        c=fake_cog(cog_module,dry=True); c.pending=set(range(20)); c.bot.get_guild=lambda _:NS(id=1)
        await c.on_raw_message_edit(NS(data={'content':'hi'},guild_id=1,channel_id=2,message_id=100))
        assert c.counters['overload']==1
    asyncio.run(run())

def test_ready_retries_if_guild_missing(cog_module):
    async def run():
        c=fake_cog(cog_module); c.bot.get_guild=lambda _:None; c._ready()
        ch=NS(id=2,name='welcome'); g=NS(id=1,text_channels=[ch],get_channel=lambda _:ch)
        c.bot.get_guild=lambda _:g; c.check_permissions=lambda _:None
        await c.on_ready(); assert c.schedule.called
    asyncio.run(run())

# Synthetic regression examples from independent review (not a held-out corpus).
@pytest.mark.parametrize("text", ["I'm Alex :)", 'im alex :3', "I'm alex lol", "I'm Alex btw", "I'm Alex (he/him)", 'im alex johnson', "hii i'm mina :)", "yo what's up im jake", 'its jake', "it's jake lol", 'this is jake', 'Ahmed here', 'hi, alex here', 'you can call me sam', 'everyone calls me bean', "I'm known as Bean", 'junior here', 'rising junior', 'just a sophomore', 'im 15m', '16 y/o', 'I graduate in 2027', "'28 here", 'taking 5 aps this year', 'currently in ap chem', 'in ap calc bc rn', "I'm doing AP Bio", 'doing ap world this year', 'I do AP Physics C', "I'm self-studying APUSH", 'preparing for ap exams', 'i do gymnastics', 'i run cross country', 'I ski', 'i sing', 'I swim competitively', 'i code in python', 'learning java', 'I do debate', "I'm in band", 'I do robotics', "I'm a gamer", "I'm a big anime fan", 'into chess', 'I teach AP Bio', 'I tutor math', "I'm a parent", "I'm a homeschooler", "I'm an engineering student", 'international student from india', 'I wanna be a surgeon', 'hoping to study medicine', 'want to be a doctor', 'my goal is a 5 in AP Bio', 'here for ap help', 'here to study', 'need help with ap chem', 'I joined for APUSH help', 'looking for study buddies', 'hi im a sophmore', 'im takin ap bio', 'im a jr taking ap chem', 'iam a freshman', 'imma junior', 'soph here', 'ngl im a junior taking 4 aps', '1. Name: Alex\n2. Grade: 11\n3. APs: AP Bio', 'Name = Alex\nGrade = 11', 'name- alex\ngrade- 11\naps- bio chem', '`Name/Nickname:` Alex', "# Hi I'm Alex", "||I'm Alex||", "I'm Alex<3", 'I`m Alex', "I'm Alex :heart:", 'hi im alex, anyone taking ap chem?', "hi I'm new, where can I find ap bio resources?"])
def test_independent_intro_regressions(text):
    assert classify(text).decision != Decision.REJECT

@pytest.mark.parametrize('text', ["I'm a junior. t.me/abc", "I'm a junior. bit.ly/abc", "Name: Sam\nGrade: junior\nhttps://scam.example/claim"])
def test_suspicious_link_flag_not_delete(text):
    verdict=classify(text)
    assert verdict.decision==Decision.KEEP and verdict.reason=='no_introduction_evidence'

def test_log_flags_are_private_links_not_copies(cog_module):
    async def run():
        c=fake_cog(cog_module); guild,ch=fake_log_guild(c)
        m=fake_message(cog_module,'new here'); await c.on_message(m)
        await c.send_deletion_log(c.log_queue.get_nowait())
        embed=ch.send.call_args.kwargs['embed']
        assert embed.title=='Welcome Message Flagged for Review'
        assert 'new here' not in embed.description and str(m.id) in embed.description
        assert embed.footer.text=='Not removed • Staff review'
    asyncio.run(run())

def test_log_allows_staff_role(cog_module):
    c=fake_cog(cog_module); guild,ch=fake_log_guild(c)
    guild.roles=[guild.default_role,NS(permissions=NS(manage_messages=True,administrator=False))]
    assert c.log_channel(guild) is ch

def test_latest_rejected_text_used_in_log_and_dm(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'hi'); latest=fake_message(cog_module,'lol')
        m.channel.fetch_message.return_value=latest
        await c.on_message(m)
        assert not m.delete.called and latest.delete.await_count==1
        assert c.dm_queue.get_nowait()[1]=='lol' and c.log_queue.get_nowait()[5]=='lol'
    asyncio.run(run())

@pytest.mark.parametrize('text',['Graduation Year: senior in college','APs: dual enrollment only','Grade: Year 13 in the UK'])
def test_unusual_template_not_deleted(text):
    assert classify(text).decision != Decision.REJECT

def test_mongo_save_timeout_cleans_old(monkeypatch):
    from utils import welcome_store
    monkeypatch.setattr(welcome_store,'SAVE_TIMEOUT',.01)
    async def run():
        s=FakeStore(); t=FakeTransport(); r=StickyReminder(s,t,1,2); await r.refresh()
        async def hang(*args): await asyncio.Event().wait()
        s.save=hang
        with pytest.raises(asyncio.TimeoutError): await r.refresh()
        assert len(t.messages)==1 and r.unsaved and r.needs_reconcile
    asyncio.run(run())
