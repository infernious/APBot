import asyncio
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from utils.welcome_validator import classify, Decision, TEMPLATE
from utils.welcome_store import StickyReminder, WelcomeStore


@pytest.mark.parametrize('text', [
    'Name: Alex\nGraduation Year: 2028\nAPs: AP Calc BC',
    'Hey everyone! I\'m a junior taking AP Bio and APUSH. I love gaming and photography!',
    "I'm Sam, class of 2029. Taking AP CSP.",
    'Name: Prefer not to say\nAPs: None yet\nInterests: Mathematics and robotics.',
    '**Name/Nickname:** Alex', '**Fun Facts/Random Deets:** chess',
    'AP Classes Taking/Taken: None', 'Class of 2029', 'My name is Mina',
    'I love photography', 'I took AP Bio', 'Hobbies: chess',
    'Name/Nickname: anonymous', 'I am a sophomore', 'I’m taking APUSH',
    'junior, AP Biology', 'Name: Alex\nAnyone taking AP Calc?',
])
def test_approve(text):
    assert classify(text).decision == Decision.APPROVE


@pytest.mark.parametrize('text', ['hi', 'hello everyone!', 'lol bro what', 'Anyone taking AP Calc?',
    TEMPLATE, 'Name: ___\nAPs: ...', 'aaaaaaaaaaaaaaaaaaaaaaaaaa', '@everyone join my server!',
    '', '   ', 'welcome to the server', '**hi**', 'Can someone help?', 'hey y’all!'])
def test_reject(text):
    assert classify(text).decision == Decision.REJECT


@pytest.mark.parametrize('text', ['数学が好きです', '2028', 'AP Calculus', 'Hi! I am here to learn.',
    'My interests are complicated', 'My favorite class is history.'])
def test_uncertain(text):
    assert classify(text).decision != Decision.REJECT


@pytest.mark.parametrize('text', ['', 'hi', TEMPLATE])
def test_attachments(text):
    assert classify(text, has_attachments=True).decision == Decision.KEEP


class FakeStore:
    def __init__(self): self.state = {'current': None, 'stale': []}; self.fail = False
    async def read(self, *args): return self.state.copy()
    async def save(self, g, c, current, stale):
        if self.fail: raise RuntimeError('database unavailable')
        self.state = {'current': current, 'stale': list(stale)}


class FakeTransport:
    def __init__(self): self.messages = set(); self.ordinary = set(); self.next = 10; self.fail_send = False; self.fail_delete = False
    async def latest_id(self): return max(self.messages | self.ordinary, default=None)
    def post_ordinary(self):
        self.next += 1; self.ordinary.add(self.next); return self.next
    async def send(self):
        if self.fail_send: raise RuntimeError('send unavailable')
        self.next += 1; self.messages.add(self.next); return self.next
    async def exists(self, mid): return mid in self.messages
    async def delete(self, mid):
        if self.fail_delete: return False
        self.messages.discard(mid); return True


def scenario(fn):
    store, transport = FakeStore(), FakeTransport()
    return asyncio.run(fn(store, transport, StickyReminder(store, transport, 1, 2)))


def test_refresh_restart():
    async def run(s,t,r):
        assert await r.refresh(ensure=True) == 11
        assert await r.refresh() == 12
        assert t.messages == {12}
        new = StickyReminder(s,t,1,2)
        assert await new.refresh(ensure=True,recovered=[12]) == 12
        assert t.messages == {12}
    scenario(run)


def test_send_failure_preserves_old():
    async def run(s,t,r):
        await r.refresh(); t.fail_send=True
        with pytest.raises(RuntimeError): await r.refresh()
        assert t.messages == {11} and s.state['current']==11
    scenario(run)


def test_failed_cleanup_retries():
    async def run(s,t,r):
        await r.refresh(); t.fail_delete=True; await r.refresh()
        assert set(s.state['stale']) == {11}
        t.fail_delete=False; await r.refresh(ensure=True)
        assert t.messages == {12} and r.stale==set()
    scenario(run)


def test_missing_sticky_recreated():
    async def run(s,t,r):
        await r.refresh(); t.messages.clear()
        assert await r.refresh(ensure=True)==12 and t.messages=={12}
    scenario(run)


def test_recover_untracked_sticky():
    async def run(s,t,r):
        await t.send(); await t.send()
        assert await r.refresh(ensure=True,recovered=[11,12])==12
        assert t.messages=={12}
    scenario(run)


def test_db_failure_cleans_old_and_recovers():
    async def run(s,t,r):
        await r.refresh(); s.fail=True
        with pytest.raises(RuntimeError): await r.refresh()
        assert t.messages=={12}
        s.fail=False; await r.refresh(ensure=True,recovered=[11,12])
        assert t.messages=={12} and s.state['current']==12
    scenario(run)


def test_store_key():
    assert WelcomeStore.key(1,2)=='1:2'


from types import SimpleNamespace
from utils.welcome_validator import resolve_channel_id, moderator_bypass

@pytest.mark.parametrize('config,expected', [
    ({}, 1), ({'channel_name': 'WELCOME'}, 1),
    ({'channel_name': 'general'}, 2), ({'channel_name': 'missing'}, None),
    ({'channel_id': 2, 'channel_name': 'welcome'}, 2),
    ({'channel_id': 99}, None), ({'channel_id': True}, None),
    ({'channel_name': ''}, None),
])
def test_channel_lookup(config, expected):
    channels = [SimpleNamespace(id=1, name='welcome'), SimpleNamespace(id=2, name='general')]
    assert resolve_channel_id(config, channels) == expected


def test_duplicate_channel_names():
    channels = [SimpleNamespace(id=1, name='welcome'), SimpleNamespace(id=2, name='welcome')]
    assert resolve_channel_id({}, channels) is None
    assert resolve_channel_id({'channel_id': 2}, channels) == 2


@pytest.mark.parametrize('name,expected', [
    ('Chat Moderator', True), ('Trial Chat Moderator', True), ('Lead Moderator', True),
    ('moderator', True), ('Admin', True), ('Senior Administrator', False), ('aDmIn Team', False), ('Member', False), ('Helper', False),
])
def test_role_name_bypass(name, expected):
    member = SimpleNamespace(roles=[SimpleNamespace(id=9, name=name)])
    assert moderator_bypass({}, member) is expected


def test_admin_permission_and_explicit_id():
    member = SimpleNamespace(roles=[SimpleNamespace(id=9, name='Helper')])
    assert moderator_bypass({'moderator_role_ids': [9]}, member)
    member.guild_permissions = SimpleNamespace(administrator=True)
    assert moderator_bypass({}, member)


def test_empty_substrings_do_not_match_everyone():
    member = SimpleNamespace(roles=[SimpleNamespace(id=9, name='Member')])
    assert not moderator_bypass({'moderator_role_name_contains': [' ', '']}, member)


def test_custom_role_names():
    member = SimpleNamespace(roles=[SimpleNamespace(id=9, name='Staff Team')])
    assert moderator_bypass({'moderator_role_name_contains': ['staff']}, member)
    assert not moderator_bypass({}, member)

def test_role_names_can_be_disabled():
    member = SimpleNamespace(roles=[SimpleNamespace(id=9, name='Admin Team')])
    assert not moderator_bypass({'moderator_role_name_contains': []}, member)


# Startup position regression tests.
def test_restart_moves_buried_reminder():
    async def run(s,t,r):
        assert await r.refresh() == 11
        member_message = t.post_ordinary()
        new = StickyReminder(s,t,1,2)
        assert await new.refresh(ensure=True,recovered=[11]) == 13
        assert t.messages == {13} and t.ordinary == {member_message}
        assert s.state['current'] == 13
    scenario(run)


def test_restart_keeps_reminder_already_at_bottom():
    async def run(s,t,r):
        t.post_ordinary()
        mid = await r.refresh()
        for _ in range(3):
            assert await r.refresh(ensure=True,recovered=[mid]) == mid
        assert t.messages == {mid} and t.next == mid
    scenario(run)


def test_restart_uses_newest_recovered_reminder():
    async def run(s,t,r):
        await r.refresh()
        t.post_ordinary()
        newest = await t.send()
        assert await r.refresh(ensure=True,recovered=[11,newest]) == newest
        assert t.messages == {newest} and s.state['current'] == newest
    scenario(run)


def test_restart_moves_reminder_outside_recovery_window():
    async def run(s,t,r):
        old = await r.refresh()
        for _ in range(55): t.post_ordinary()
        newest = await r.refresh(ensure=True,recovered=[])
        assert newest > old and t.messages == {newest}
        assert len(t.ordinary) == 55
    scenario(run)


def test_restart_send_failure_keeps_old_reminder():
    async def run(s,t,r):
        old = await r.refresh()
        t.post_ordinary()
        t.fail_send = True
        with pytest.raises(RuntimeError):
            await r.refresh(ensure=True,recovered=[old])
        assert t.messages == {old} and s.state['current'] == old
    scenario(run)


def test_restart_moves_buried_untracked_reminder():
    async def run(s,t,r):
        old = await t.send()
        member_message = t.post_ordinary()
        newest = await r.refresh(ensure=True,recovered=[old])
        assert t.messages == {newest} and t.ordinary == {member_message}
    scenario(run)


# Conservative, whole-message slang normalization regression tests.
@pytest.mark.parametrize('text', [
    'LOOOOOOOOOOOOL', 'LOOOLLL', 'LOLLLLL', 'LMAOOOOOO', 'LMFAOOOO',
    'BRUHHHHHH', 'NOOOOOOO', 'HAHAHAHAHAHA', 'HEHEHEHE',
    'loooool!!!', 'LOL BRUHHH', 'OMG LOL', 'hiiiiii', 'heyyyyyy',
    'bro what are you talking about', 'BROOO what are you talking about?!',
    'what do you mean?', 'bro what do you mean', 'how are you guys?',
    'asdfasdfasdf', 'qwerqwer', 'aAaAaAaAaA!!!',
])
def test_obvious_chat_variants(text):
    assert classify(text).decision == Decision.REJECT


@pytest.mark.parametrize('text', [
    'lol I love math', 'hiiii im a sophomore taking ap world lol',
    'Name: Lool', 'Hobbies: laughing and gaming lol',
    'APs: None yet', 'I love photography hahaha',
    'Name: N/A\nAPs: AP Bio', 'My name is Haha',
    'professional procrastinator', 'math nerd, class of 28',
    '数学が好きです', 'LOL is my favorite game',
    'I play League of Legends (LOL)', 'hi I am here to learn',
    'bro I am a junior taking AP Bio',
])
def test_do_not_delete_possible_introduction(text):
    assert classify(text).decision != Decision.REJECT


@pytest.mark.parametrize('text', ['LOOOOOOOOOOOOL', 'BRUHHHH', 'asdfasdf'])
def test_attachment_safety_preserved(text):
    assert classify(text, has_attachments=True).decision == Decision.KEEP


@pytest.mark.parametrize('text', [
    'LMOAAAAAAAAAAAAAAA', 'MONAAAAAAAAAAAAAAAAAAAAAAAAAA',
    'TROLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL', 'WHAAAAAAAAT',
    'AAAAAAAAB', 'bOOOOOOOOOOOOoo!!!', 'yessssssssssssss',
    'Trollllllllllllllllll?',
])
def test_extreme_standalone_stretch(text):
    assert classify(text).decision == Decision.REJECT


@pytest.mark.parametrize('text', [
    'Name: Mona', 'Name: Aarav', 'Name: Troll', 'Name: bookkeeper',
    'Name: MONAAAAAAAAAAAAAAAAAAAA', 'My name is MONAAAAAAAAAAAA',
    'I love math sooooooooo much', '数学が好きです',
    'TROLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLLL is my nickname',
])
def test_stretch_intro_safety(text):
    assert classify(text).decision != Decision.REJECT


def test_stretched_attachment_safety():
    assert classify('MONAAAAAAAAAAAAAAAAAAAA', has_attachments=True).decision == Decision.KEEP
