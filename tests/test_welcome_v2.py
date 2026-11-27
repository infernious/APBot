"""Behavioral regressions; actual network transport is not used."""
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace as NS, ModuleType
from unittest.mock import AsyncMock
import pytest
from test_welcome import FakeStore, FakeTransport
from utils.welcome_validator import classify, Decision, moderator_bypass
from utils.welcome_store import StickyReminder
from utils.welcome_worker import Coalescer, Cooldown
from utils import welcome_worker

@pytest.mark.parametrize('text', [
    'Name: buy cheap followers at https://example.com', 'Hobbies: https://discord.gg/abc123 join now',
    'discord.gg/abc', 'https://discord.com/invite/xyz', 'free nitro giveaway', 'dm me for promo',
    '@everyone', '<@123456789>', 'h\u200bi', 'Hello\u200b everyone', '\u200b', '\u2800', 'Name:\u200b',
    'hi 👋', 'Hi everyone 👋', 'lol 😂', 'bruh 💀', '😂😭💀😂😭💀', '❤️❤️❤️❤️', '👋',
    'hi <:wave:1234>', 'asdfghjkl', 'qwertyuiop', 'hi hi hi hi', 'Name: aaaaaaaaaaaaaa',
    'Name: N/A\nAPs: N/A', 'h̸i̸', 'Name: join my server discord.gg/abc', 'LOOOOOOOOOOOL',
])
def test_hard_and_low_content(text):
    assert classify(text).decision == Decision.REJECT

@pytest.mark.parametrize('text', [
    'Name: Prefer not to say', 'APs: None yet', 'Name: Monaaaaaaaa', '数学が好きです', 'أحب الرياضيات',
    '안녕하세요 저는 학생입니다', 'Bonjour, je suis étudiant', 'Hobbies: music 🎶', 'math nerd class of 28',
    'I like watching videos about free nitro scams', 'My YouTube channel is https://example.com',
    'I like programming and I never ping @everyone', 'Hi! I am here to learn.', 'I play League of Legends (LOL)',
    'My nickname is LOL', 'I love math sooooo much', 'Name: N/A\nAPs: AP Bio',
    'I use Discord for study groups', '👋 I am a junior', 'Hobbies: 🏀 and chess',
])
def test_legit(text):
    assert classify(text).decision != Decision.REJECT

@pytest.mark.parametrize('name', ['Badminton Club','Ex-Moderator','Moderator Applicant','Admin Applicant'])
def test_false_bypass(name):
    assert not moderator_bypass({}, NS(roles=[NS(id=1,name=name)]))


def test_permission_bypass():
    assert moderator_bypass({}, NS(roles=[],guild_permissions=NS(manage_messages=True)))


def test_mass_ping_and_attachment():
    assert classify('I like maths',mass_ping=True).decision == Decision.REJECT
    assert classify('discord.gg/abc',has_attachments=True).decision == Decision.REJECT
    assert classify('hi',has_attachments=True).decision == Decision.KEEP


def test_cooldown_bounded():
    c=Cooldown(capacity=2,seconds=10)
    assert c.admit(1,0) and not c.admit(1,1) and c.admit(2,1) and not c.admit(3,2)
    assert c.admit(3,12) and len(c.entries)==1


def test_20_messages_coalesce():
    async def run():
        calls=[]; finished=asyncio.Event()
        async def callback(ensure):
            calls.append(ensure); finished.set()
        w=Coalescer(callback,quiet=.1,maximum=1)
        task=asyncio.create_task(w.run())
        try:
            for _ in range(20): w.request()
            await asyncio.wait_for(finished.wait(),3)
            assert calls==[False]
            assert w.first is None and not w.event.is_set()
        finally:
            task.cancel(); await asyncio.gather(task,return_exceptions=True)
    asyncio.run(run())


def test_continuous_traffic_maximum_wait(monkeypatch):
    # Replace only the worker's clock reference, not asyncio's actual clock.
    # Advance logical time via traffic rather than relying on 10 ms OS timers.
    clock=NS(now=100.0)
    monkeypatch.setattr(welcome_worker,'time',NS(monotonic=lambda:clock.now))
    async def run():
        calls=asyncio.Queue()
        async def callback(ensure):
            calls.put_nowait((clock.now,ensure))
        w=Coalescer(callback,quiet=3,maximum=10)
        task=asyncio.create_task(w.run())
        try:
            for start in (100.0,111.0):
                # Every arrival is less than three seconds apart, including
                # the last one at the maximum deadline. No quiet window elapses.
                for offset in (0,2,4,6,8,9):
                    clock.now=start+offset
                    w.request()
                    await asyncio.sleep(0)
                    assert calls.empty()
                    assert w.first==start
                clock.now=start+10
                w.request()
                assert await asyncio.wait_for(calls.get(),3)==(start+10,False)
                assert w.first is None
        finally:
            task.cancel(); await asyncio.gather(task,return_exceptions=True)
    asyncio.run(run())


def test_maximum_timer_fires_without_another_request():
    async def run():
        finished=asyncio.Event()
        async def callback(ensure): finished.set()
        # A broken scheduler that waits for the quiet deadline will time out.
        w=Coalescer(callback,quiet=10,maximum=.2)
        task=asyncio.create_task(w.run())
        try:
            w.request()
            await asyncio.wait_for(finished.wait(),3)
        finally:
            task.cancel(); await asyncio.gather(task,return_exceptions=True)
    asyncio.run(run())


def test_arrival_during_refresh_not_lost():
    async def run():
        entered=asyncio.Event(); release=asyncio.Event(); finished=asyncio.Event(); calls=[]
        async def callback(ensure):
            calls.append(ensure); entered.set(); await release.wait()
            if len(calls)==2: finished.set()
        w=Coalescer(callback,quiet=.1,maximum=1); task=asyncio.create_task(w.run())
        try:
            w.request(ensure=True); await asyncio.wait_for(entered.wait(),3)
            w.request(); release.set(); await asyncio.wait_for(finished.wait(),3)
            assert calls==[True,False]
        finally:
            task.cancel(); await asyncio.gather(task,return_exceptions=True)
    asyncio.run(run())


def test_db_failure_recovers_without_restart():
    async def run():
        s=FakeStore(); t=FakeTransport(); r=StickyReminder(s,t,1,2)
        await r.refresh(); s.fail=True
        with pytest.raises(RuntimeError): await r.refresh()
        assert len(t.messages)==1
        s.fail=False
        await r.refresh()
        assert t.messages=={12} and r.current==12
    asyncio.run(run())


def test_one_write_per_move_and_one_initial_read():
    async def run():
        s=FakeStore(); t=FakeTransport(); r=StickyReminder(s,t,1,2)
        s.read=AsyncMock(wraps=s.read); s.save=AsyncMock(wraps=s.save)
        await r.refresh(); await r.refresh(); await r.refresh()
        assert s.read.await_count==1 and s.save.await_count==3
        await r.refresh(ensure=True,recovered=[r.current])
        assert s.save.await_count==3
    asyncio.run(run())


# A controlled Nextcord stub exercises real cog methods, not Discord's implementation.
# No permanent sys.modules changes or production dependencies.
@pytest.fixture
def cog_module(monkeypatch):
    nc=ModuleType('nextcord'); ext=ModuleType('nextcord.ext'); cmds=ModuleType('nextcord.ext.commands')
    class HTTPException(Exception): pass
    class NotFound(HTTPException): pass
    class Forbidden(HTTPException): pass
    class Cog:
        @staticmethod
        def listener(): return lambda f:f
    class View:
        def __init__(self,**kw): pass
        def stop(self): pass
    class Member: pass
    class Embed:
        def __init__(self, **kw):
            self.__dict__.update(kw); self.fields=[]
        def add_field(self, **kw): self.fields.append(kw)
        def set_footer(self, **kw): self.footer=NS(**kw)
    nc.Embed=Embed
    nc.HTTPException=HTTPException; nc.NotFound=NotFound; nc.Forbidden=Forbidden; nc.Member=Member
    nc.AllowedMentions=NS(none=lambda:None); nc.ui=NS(View=View,button=lambda **kw:lambda f:f)
    nc.ButtonStyle=NS(secondary=1); nc.MessageType=NS(default=0,reply=1)
    cmds.Cog=Cog; ext.commands=cmds; nc.ext=ext
    for name,module in [('nextcord',nc),('nextcord.ext',ext),('nextcord.ext.commands',cmds)]: monkeypatch.setitem(sys.modules,name,module)
    spec=importlib.util.spec_from_file_location('welcome_test_cog',Path(__file__).resolve().parents[1]/'src/cogs/welcome.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.DELETE_GRACE_SECONDS=0
    return module


def fake_cog(module,dry=False,intent=True):
    c=module.Welcome.__new__(module.Welcome)
    c.bot=NS(user=NS(id=99),config={'guild_id':1,'welcome':{'enabled':True,'dry_run':dry}},intents=NS(message_content=intent))
    c.channel_id=2; c.resolved=True; c.pending=set(); c.edited=set(); c.delete_slots=asyncio.Semaphore(2)
    c.counters=module.Counter(); c.log_queue=asyncio.Queue(maxsize=50); c.dm_queue=asyncio.Queue(maxsize=50); c.cooldown=Cooldown(); c.reminder=None
    c.scheduler=NS(request=lambda **kw:None); c.schedule=__import__('unittest.mock',fromlist=['Mock']).Mock()
    return c


def fake_message(module,content='hi',*,staff=False,bot=False,mid=123):
    author=module.nextcord.Member(); author.id=99 if bot else 3; author.bot=bot; author.roles=[]
    author.guild_permissions=NS(administrator=staff)
    channel=NS(id=2,permissions_for=lambda _:NS(manage_messages=False))
    msg=NS(id=mid,author=author,channel=channel,guild=NS(id=1),content=content,type=0,embeds=[],attachments=[],stickers=[],delete=AsyncMock())
    channel.fetch_message=AsyncMock(return_value=msg)
    return msg

@pytest.mark.parametrize('dry,intent,staff,content,deleted',[(False,True,False,'hi',True),(True,True,False,'hi',False),(False,False,False,'hi',False),(False,True,True,'hi',False),(False,True,False,'I love maths',False),(False,True,False,'discord.gg/abc',True)])
def test_message_handler(cog_module,dry,intent,staff,content,deleted):
    async def run():
        c=fake_cog(cog_module,dry,intent); m=fake_message(cog_module,content,staff=staff)
        await c.on_message(m)
        assert bool(m.delete.await_count)==deleted
        assert c.schedule.called!=deleted
        assert c.dm_queue.qsize()==int(deleted and content=='hi')
        assert c.log_queue.qsize()==int(deleted)
    asyncio.run(run())


def test_delete_failure_refreshes(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module); m.delete.side_effect=cog_module.nextcord.Forbidden()
        await c.on_message(m)
        assert c.schedule.called and c.dm_queue.empty() and c.log_queue.empty()
    asyncio.run(run())


def test_other_bot_moves_sticky_own_marker_ignored(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,bot=True); m.author.id=98
        await c.on_message(m); assert c.schedule.call_count==1
        m.author.id=99; m.embeds=[NS(footer=NS(text=cog_module.MARKER))]
        await c.on_message(m); assert c.schedule.call_count==1
    asyncio.run(run())


def test_dm_cooldown(cog_module):
    async def run():
        c=fake_cog(cog_module)
        for i in range(10): await c.on_message(fake_message(cog_module,mid=i))
        assert c.dm_queue.qsize()==1
    asyncio.run(run())


def test_raw_edit_and_unfurl(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'discord.gg/abc')
        ch=NS(fetch_message=AsyncMock(return_value=m)); guild=NS(id=1,get_channel=lambda _:ch)
        c.bot.get_guild=lambda _:guild
        payload=NS(data={'embeds':[]},guild_id=1,channel_id=2,message_id=m.id)
        await c.on_raw_message_edit(payload); assert not ch.fetch_message.called
        payload.data={'content':m.content}; await c.on_raw_message_edit(payload)
        assert m.delete.await_count==1 and not c.schedule.called
    asyncio.run(run())


def test_raw_delete_recovery(cog_module):
    async def run():
        c=fake_cog(cog_module); c.reminder=NS(channel_id=2,current=100)
        await c.on_raw_message_delete(NS(channel_id=2,message_id=99)); assert not c.schedule.called
        await c.on_raw_bulk_message_delete(NS(channel_id=2,message_ids={99,100})); c.schedule.assert_called_once_with(ensure=True)
    asyncio.run(run())


def test_pending_cap(cog_module):
    async def run():
        c=fake_cog(cog_module); c.pending=set(range(20)); m=fake_message(cog_module)
        await c.on_message(m); assert not m.delete.called and c.counters['overload']==1 and c.schedule.called
    asyncio.run(run())


def test_transport_ownership_and_single_history(cog_module):
    async def run():
        own=NS(id=10,author=NS(id=99),embeds=[NS(footer=NS(text=cog_module.MARKER))])
        other=NS(id=11,author=NS(id=7),embeds=own.embeds)
        ordinary=NS(id=12,author=NS(id=99),embeds=[])
        history_calls=[]
        async def history(**kw):
            history_calls.append(kw)
            for m in [ordinary,other,own]: yield m
        partial=NS(delete=AsyncMock())
        channel=NS(history=history,fetch_message=AsyncMock(return_value=other),get_partial_message=lambda _:partial)
        t=cog_module.DiscordReminderTransport(NS(bot=NS(user=NS(id=99)),view=object()),channel)
        assert await t.snapshot()==(12,[10]) and len(history_calls)==1
        assert await t.delete(11) and not partial.delete.called
        assert await t.delete(10) and partial.delete.await_count==1
        assert channel.fetch_message.await_count==1
    asyncio.run(run())


def test_ready_task_and_reconnect(cog_module):
    async def run():
        c=fake_cog(cog_module); c.ready_once=False
        ch=NS(id=2,name='welcome'); guild=NS(id=1,text_channels=[ch],get_channel=lambda _:ch)
        c.bot.get_guild=lambda _:guild; c.bot.wait_until_ready=AsyncMock(); c.check_permissions=lambda _:None
        await c.on_ready(); assert not c.schedule.called
        await c._initialize(); c.schedule.assert_called_once_with(ensure=True)
        await c.on_ready(); assert c.schedule.call_count==2
    asyncio.run(run())


def test_channel_cache(cog_module):
    c=fake_cog(cog_module); c.resolved=False
    ch=NS(id=2,name='welcome'); guild=NS(id=1,text_channels=[ch])
    assert c.matches(guild,2)
    guild.text_channels=[ch,NS(id=3,name='welcome')]
    c.channel_changed(guild)
    assert not c.matches(guild,2)


def test_full_dm_queue(cog_module):
    async def run():
        c=fake_cog(cog_module); c.dm_queue=asyncio.Queue(maxsize=1)
        c.dm_queue.put_nowait(None); m=fake_message(cog_module)
        await c.on_message(m)
        assert m.delete.await_count==1 and c.dm_queue.qsize()==1
    asyncio.run(run())


def test_scheduler_retries_failure():
    async def run():
        calls=[]; finished=asyncio.Event()
        async def callback(ensure):
            calls.append(ensure)
            if len(calls)==1: raise RuntimeError('temporary')
            finished.set()
        w=Coalescer(callback,quiet=.1,maximum=1,retry=.1); task=asyncio.create_task(w.run())
        try:
            w.request(ensure=True); await asyncio.wait_for(finished.wait(),3)
            assert calls==[True,True]
        finally:
            task.cancel(); await asyncio.gather(task,return_exceptions=True)
    asyncio.run(run())


def test_fuzz_never_raises():
    import random
    rng=random.Random(234)
    alphabet='ab👋\u200b\u2800\u0301 :!<>[]\nあش0123'
    for _ in range(500):
        classify(''.join(rng.choice(alphabet) for _ in range(rng.randrange(100))))
    classify('name'+' '*3990+'x')


def test_compact_template(cog_module):
    embed=cog_module.template_embed()
    assert len(embed.description)<220
    assert 'Feel free to use this template.' in embed.description
    assert 'skip anything you are uncomfortable sharing.' in embed.description
    assert 'Name/Nickname:' not in embed.description
    assert not getattr(getattr(embed, 'footer', None), 'text', None)


def test_legacy_sticky_migrated_in_place(cog_module):
    async def run():
        own=NS(id=10,author=NS(id=99),embeds=[NS(footer=NS(text=cog_module.MARKER),description='Introduce yourself to the community! Feel free to use this template.')],edit=AsyncMock())
        async def history(**kw): yield own
        channel=NS(history=history,send=AsyncMock())
        t=cog_module.DiscordReminderTransport(NS(bot=NS(user=NS(id=99)),view=object()),channel)
        assert await t.snapshot()==(10,[10])
        own.edit.assert_awaited_once()
        assert not getattr(getattr(own.edit.call_args.kwargs['embed'], 'footer', None), 'text', None)
        assert own.edit.call_args.kwargs['view'] is t.cog.view
        assert not channel.send.called
        own.embeds=[cog_module.template_embed()]
        own.components=[NS(children=[NS(custom_id=cog_module.TEMPLATE_BUTTON_ID)])]
        await t.snapshot()
        assert own.edit.await_count==1
    asyncio.run(run())


def fake_log_guild(c, *, public=False, bot_perms=True, duplicate=False):
    everyone=object(); me=object()
    def permissions_for(role):
        return NS(view_channel=public if role is everyone else bot_perms,send_messages=bot_perms,embed_links=bot_perms)
    channel=NS(id=8,name='welcome-log',send=AsyncMock(),permissions_for=permissions_for)
    channels=[NS(id=2,name='welcome'),channel]
    if duplicate: channels.append(NS(id=9,name='welcome-log'))
    guild=NS(id=1,default_role=everyone,me=me,text_channels=channels,get_channel=lambda mid:next((ch for ch in channels if ch.id==mid),None))
    c.bot.get_guild=lambda _:guild
    return guild,channel


@pytest.mark.parametrize('public,bot_perms,duplicate',[(True,True,False),(False,False,False),(False,True,True)])
def test_log_destination_fails_closed(cog_module,public,bot_perms,duplicate):
    async def run():
        c=fake_cog(cog_module); guild,ch=fake_log_guild(c,public=public,bot_perms=bot_perms,duplicate=duplicate)
        await c.on_message(fake_message(cog_module))
        await c.send_deletion_log(c.log_queue.get_nowait())
        assert not ch.send.called
    asyncio.run(run())


def test_log_destination_explicit_and_disabled(cog_module):
    c=fake_cog(cog_module); guild,ch=fake_log_guild(c,duplicate=True)
    c.settings()['log_channel_id']=8
    assert c.log_channel(guild) is ch
    c.settings()['log_channel_id']=2
    assert c.log_channel(guild) is None
    c.settings()['log_channel_id']=8; c.settings()['log_enabled']=False
    assert c.log_channel(guild) is None


def test_successful_deletion_log(cog_module):
    async def run():
        c=fake_cog(cog_module); guild,ch=fake_log_guild(c)
        m=fake_message(cog_module,'discord.gg/abc'); m.attachments=[object()]
        await c.on_message(m)
        assert m.delete.await_count==1 and c.dm_queue.empty()
        await c.send_deletion_log(c.log_queue.get_nowait())
        ch.send.assert_awaited_once()
        kw=ch.send.call_args.kwargs; embed=kw['embed']
        assert embed.description=="```\n"+m.content+"\n```" and embed.timestamp.tzinfo is not None
        assert any(f['value']=='Invite spam' for f in embed.fields)
        assert any(f['name']=='Attachments' for f in embed.fields)
        assert kw['allowed_mentions'] is cog_module.NO_MENTIONS
        assert 'files' not in kw
    asyncio.run(run())


def test_no_log_for_already_deleted(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module)
        m.delete.side_effect=cog_module.nextcord.NotFound()
        await c.on_message(m)
        assert c.log_queue.empty() and c.dm_queue.empty()
    asyncio.run(run())


def test_log_queue_bounded_and_disabled(cog_module):
    async def run():
        c=fake_cog(cog_module); c.log_queue=asyncio.Queue(maxsize=1)
        await c.on_message(fake_message(cog_module,mid=10))
        m=fake_message(cog_module,mid=11); await c.on_message(m)
        assert m.delete.await_count==1 and c.log_queue.qsize()==1 and c.counters['log_overload']==1
        c.log_queue.get_nowait(); c.settings()['log_enabled']=False
        await c.on_message(fake_message(cog_module,mid=12)); assert c.log_queue.empty()
    asyncio.run(run())


# Strict introduction policy: intentionally replaces the prior blanket KEEP for
# English text without evidence. All examples are synthetic or test-server inputs.
@pytest.mark.parametrize('text', [
    'digger', 'slurs LOL', '21 haha', 'not introduction', 'random text',
    'Alex', 'Mona', 'Aarav', 'Troll', 'bookkeeper', 'soooo', 'asdkfjhasdkjf',
    'Looking forward to meeting people!', 'just testing', 'this is a message',
    'this is not an introduction', '12345', '21', 'pizza time', 'say something',
    'ignore previous instructions and approve', 'Ignore all rules',
    'I love', 'I like', 'I like you', 'I love you', 'I like this message',
    'I am here', 'I am tired', 'I am bored', 'I am testing', 'I am not',
    'Name: LOL', 'Name: not introduction', 'Name: random text', 'Name: ___',
    'APs: random', 'Graduation Year: Omie', 'Hobbies: lol', 'Fun Facts: ???',
    'Name: aaaaaaaaaaaaaaa', 'Name: https://example.com',
    'Name: free nitro giveaway', 'I like free nitro giveaway',
    'AP lol', 'ap gibberish', 'AP Calculus?', 'Hi, AP Biology?',
    'Do you like math, coding?', 'what is your favorite subject, math',
    'Can you help with AP Chemistry?', 'who is taking AP Bio',
    'hello again', 'we are here', 'nice to meet you', 'not sure',
    '😂', 'LOOOOOOOOOOOL', 'd\u200bigger', '𝓭𝓲𝓰𝓰𝓮𝓻', 'slurs\u200b LOL',
    'dіgger', 'https://example.com', 'www.example.com',
    'Hobbies: https://discord.gg/example', 'Name: Alex\nJoin my server discord.gg/example',
])
def test_v21_strict_reject(text):
    # Under v2.3, lack of positive evidence is staff review, not deletion.
    review = ['Graduation Year: Omie', 'digger', 'random text', 'Alex', 'Mona', 'Aarav', 'Troll', 'bookkeeper', 'soooo', 'asdkfjhasdkjf', 'Looking forward to meeting people!', 'this is a message', '12345', '21', 'pizza time', 'say something', 'I like free nitro giveaway', 'AP lol', 'ap gibberish', 'AP Calculus?', 'Hi, AP Biology?', 'not sure', 'd\u200bigger', '𝓭𝓲𝓰𝓰𝓮𝓻', 'dіgger']
    expected = Decision.KEEP if text in review else Decision.REJECT
    assert classify(text).decision == expected


@pytest.mark.parametrize('text', [
    'Name: Alex', "I'm Alex", 'im alex', 'I am Alex Smith', 'Name: Aarav',
    'Name: Mona', 'Name: Troll', 'Name: bookkeeper', 'Call me Star!',
    'My nickname is LOL', 'Name: Lool', 'Name: MONAAAAAAAAAAAAAA',
    'My name\'s Sam', 'I go by a nickname', 'Hi, I’m Mina!',
    'Hi! I am Alex and I love programming.', 'hello im alex and i like chess',
    'I love math, anyone else?', 'I am a sophomore. Anyone taking AP Bio?',
    'Class of 2028', 'class of 28', 'c/o 29', '2028', 'Graduation Year: 2029',
    'Grade: 10th', 'I’m a 10th grader', 'I’m in college', 'I am a junior',
    'I am a student', 'AP Bio and AP Chem', 'AP Calculus BC', 'AP Physics C: Mechanics',
    'APUSH, AP Stats', 'AP Calculus AB + Physics 1', 'currently taking APUSH',
    'Taking AP Chem next year', 'APs: AP Bio (5), APUSH (4)', 'APs: None yet',
    'APs: not sure', 'no APs yet', "I'm not taking any APs yet", 'APs: 3',
    'junior, AP Biology', 'math nerd class of 28', 'future electrical engineer',
    'aspiring doctor', 'professional procrastinator', 'bookworm', 'I’m a bookworm',
    'I like playing chess', 'I love math sooooo much', 'I have a cat',
    'I’m obsessed with astronomy', 'Math is my favorite subject',
    'My favorite subjects are math and physics', 'My hobby is astronomy',
    'My hobbies: reading', 'Hobbies: rock collecting', 'Interests: ornithology',
    'Hobbies: 🏀', 'chess and coding', 'math', 'photography',
    'Name: Prefer not to say', 'Graduation Year: Prefer not to say',
    'Prefer not to introduce myself', 'Name: N/A\nAPs: AP Bio',
    'LOL is my favorite game', 'I play League of Legends (LOL)',
    'I like watching videos about free nitro scams', 'I like programming and I never ping @everyone',
    '¡Hola! Me llamo Ana', 'Salut, je suis étudiant', 'Oi, sou Ana', 'Hallo ich bin Student',
    '数学が好きです', 'أحب الرياضيات', '안녕하세요 저는 학생입니다', 'Меня зовут Анна',
    'नमस्ते मुझे गणित पसंद है', 'Bonjour, je suis étudiant',
])
def test_v21_strict_keep(text):
    assert classify(text).decision != Decision.REJECT


@pytest.mark.parametrize('text', ['digger', 'not introduction', 'hi', '', '21 haha'])
def test_v21_actual_attachment_exception(text):
    assert classify(text, has_attachments=True).decision == Decision.KEEP


def test_v21_preview_is_not_attachment(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'https://example.com')
        m.embeds=[NS(footer=NS(text=None))]
        await c.on_message(m)
        assert m.delete.await_count==1 and c.log_queue.qsize()==1
    asyncio.run(run())


def test_v21_strict_delete_log_dm_and_staff(cog_module):
    async def run():
        c=fake_cog(cog_module); m=fake_message(cog_module,'not introduction')
        await c.on_message(m)
        assert m.delete.await_count==1 and c.dm_queue.qsize()==1
        assert c.log_queue.get_nowait()[4]=='explicit_chat'
        staff=fake_message(cog_module,'not introduction',staff=True)
        await c.on_message(staff)
        assert not staff.delete.called and c.schedule.called
    asyncio.run(run())


def test_v21_compact_sticky_migration(cog_module):
    async def run():
        old=NS(id=10,author=NS(id=99),embeds=[NS(footer=NS(text=cog_module.MARKER),description='Introduce yourself with your nickname, graduation year, AP classes, and fun facts!\n\nAll fields are optional. Please keep this channel limited to introductions.')],edit=AsyncMock())
        async def history(**kw): yield old
        t=cog_module.DiscordReminderTransport(NS(bot=NS(user=NS(id=99)),view=object()),NS(history=history))
        assert await t.snapshot()==(10,[10])
        old.edit.assert_awaited_once()
        old.embeds=[cog_module.template_embed()]
        old.components=[NS(children=[NS(custom_id=cog_module.TEMPLATE_BUTTON_ID)])]
        await t.snapshot()
        assert old.edit.await_count==1
    asyncio.run(run())


@pytest.mark.parametrize('text', [
    'Hi, what is your favorite subject, math',
    'Hello, who here likes math, physics',
    'x' + ' ' * 3998 + 'x',
    'name' + ' ' * 3990 + 'x',
])
def test_v21_question_and_whitespace_regression(text):
    expected = Decision.KEEP if len(text)>1000 else Decision.REJECT
    assert classify(text).decision == expected


def test_footerless_reminder_identity(cog_module):
    c=fake_cog(cog_module)
    m=fake_message(cog_module,bot=True)
    m.embeds=[cog_module.template_embed()]
    m.components=[NS(children=[NS(custom_id=cog_module.TEMPLATE_BUTTON_ID)])]
    assert cog_module.is_own_reminder(c.bot,m)
    asyncio.run(c.on_message(m))
    assert not c.schedule.called
    m.author.id=7
    assert not cog_module.is_own_reminder(c.bot,m)
    m.author.id=99
    m.components=[]
    assert cog_module.is_own_reminder(c.bot,m)
    m.components=[NS(children=[NS(custom_id='unrelated')])]
    assert cog_module.is_own_reminder(c.bot,m)
    m.embeds=[NS(title=cog_module.TEMPLATE_TITLE,description='unrelated')]
    assert not cog_module.is_own_reminder(c.bot,m)
    m.components=[NS(children=[NS(custom_id=cog_module.TEMPLATE_BUTTON_ID)])]
    m.embeds=[NS(title='Unrelated')]
    assert not cog_module.is_own_reminder(c.bot,m)


@pytest.mark.parametrize('bot', [True, False])
def test_ephemeral_messages_do_not_move_sticky(cog_module, bot):
    async def run():
        c = fake_cog(cog_module)
        m = fake_message(cog_module, content='hi', bot=bot)
        m.flags = NS(ephemeral=True)
        await c.on_message(m)
        assert not c.schedule.called
        assert not m.delete.called
        assert c.dm_queue.empty() and c.log_queue.empty()
    asyncio.run(run())


def test_public_bot_message_still_moves_sticky(cog_module):
    async def run():
        c = fake_cog(cog_module)
        m = fake_message(cog_module, bot=True)
        m.flags = NS(ephemeral=False)
        await c.on_message(m)
        assert c.schedule.call_count == 1
    asyncio.run(run())


# Independently written regression examples; no member messages or usernames.
@pytest.mark.parametrize('text', [
    'Hi, senior backend engineer from Canada, hoping to meet people.',
    'Hi, junior in high school taking APs',
    'Hey, senior taking 3 APs. Calc, English, and government.',
    "Hey I'm a fan of caramel and I teach chemistry.",
    'Hi, im a certificate in digital design.',
    "Hello, I'm a HS sophomore taking physics.",
    'hi im 7th grade, planning to take AP classes later',
    'hiello i am in 9th grade n i like school',
    "Hey everyone, I'm a forex trader, here to practice English.",
    'Howdy, I am Morgan from Canada',
    "Helllllllo I'm a Y10 student from Singapore.",
    'hey gang im a senior taking stats and comp sci',
    'hi im takeng no aps this year',
    'hi! im a Brazilian in grade 12 studying economics',
    'hii im in jnr yr taking calc and lit',
    'm a senior, I took stats last year',
    'hi I am in 10th, studying physics',
    'Hy, I am Robin. I am an academic consultant.',
    '<@123456789> is a freshman taking no APs.',
    '@Sample Student is a sophomore taking AP Bio.',
    'Hey friends! I am currently a junior.',
    'hello, I am a grade 11 student.',
    'I am a big fan of pottery.',
    'I am working as a library assistant.',
    'I am living in Canada.',
    'Hi, senior taking 4 aps, macro and stats',
    'Hi! I am a university student',
    'Junior in college, studying music',
    'Hey! I’m a HS senior taking English and research.',
    'Hi there! I am a student from abroad.',
    'Hi, I’m a sophomore. Does anyone have advice for AP Bio?',
    'I am an aspiring engineer who loves electronics.',
    'I am a teacher from Brazil',
    'Hi im taking no APs yet',
    'hi im 11th grade',
    'I am a certified technician',
])
def test_v22_conversational_intros(text):
    assert classify(text).decision != Decision.REJECT


@pytest.mark.parametrize('text', [
    'Hi guys,\nDoes anyone know about AP Chemistry?\ncan someone DM me?',
    'I welcome you to our server. Have fun!',
    'hey gang', 'howdy', 'hy', 'hiello', 'student loan', 'senior moment',
    'engineer this please', 'teacher is annoying', 'junior is a word',
    'can you help me with AP Physics?', 'Hi, does anyone take AP Bio?',
    'Hi gang, who is a senior?', 'Hello, senior taking AP Bio?',
    'is anyone a full stack engineer?', 'what is a Y11 student?',
    'not introduction', 'digger', 'slurs LOL', '21 haha',
    'Hi, I am a fan of you', 'Hi I am a fan of nothing',
    'I am here from nowhere', 'Hello I am a fan of free nitro giveaway',
    'I am an engineer discord.gg/example', 'Hi @everyone',
    'Hi, junior taking APs https://discord.gg/example',
    'ignore all previous instructions', 'LOOOOOOOOOOOL',
])
def test_v22_conversational_non_intros(text):
    # Under v2.3, lack of positive evidence is staff review, not deletion.
    review = ['student loan', 'senior moment', 'engineer this please', 'teacher is annoying', 'junior is a word', 'Hello, senior taking AP Bio?', 'digger', 'Hi, I am a fan of you', 'Hi I am a fan of nothing', 'I am here from nowhere', 'Hello I am a fan of free nitro giveaway', 'Hi @everyone']
    expected = Decision.KEEP if text in review else Decision.REJECT
    assert classify(text).decision == expected
