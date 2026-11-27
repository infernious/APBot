import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from utils.appeal_policy import *


import utils.appeal_policy as policy_module
from types import SimpleNamespace as NS


@pytest.fixture(autouse=True)
def mock_test_identity(monkeypatch):
    monkeypatch.setattr(policy_module, "TEST_MAIN_GUILD_ID", 1)
    monkeypatch.setattr(policy_module, "TEST_BOT_ID", 5)


def config(test=True, **overrides):
    return {"guild_id":1 if test else 11, "ban_appeal_server":2 if test else 12,
            "appeals_channel_id":3 if test else 13, "application_id":5 if test else 15, **overrides}


def test_test_timing():
    p=AppealPolicy.load(config(),TEST_DATABASE)
    assert (p.review,p.reminder,p.cooldown,p.poll)==(300,120,300,5)
    assert p.snapshot(100)=={'deadline_at':400,'reminder_at':280,'cooldown_seconds':300,'reminder_max_votes':3}


def test_prod_defaults():
    p=AppealPolicy.load(config(False),'ap-students')
    assert (p.review,p.reminder,p.cooldown,p.poll)==(1209600,172800,7257600,60)


@pytest.mark.parametrize('key,value',[('guild_id',0),('guild_id',True),('guild_id','1'),
    ('guild_id',99),('application_id',99),('application_id',None),('ban_appeal_server',1),
    ('ban_appeal_server',0),('appeals_channel_id',None)])
def test_bad_config(key,value):
    with pytest.raises(ValueError): AppealPolicy.load(config(**{key:value}),TEST_DATABASE)


@pytest.mark.parametrize('key,value',[('TEST_REVIEW',0),('TEST_REMINDER',300),('TEST_REMINDER',0),
    ('TEST_COOLDOWN',-1),('TEST_MAX_VOTES',-1),('TEST_REVIEW',True)])
def test_bad_timers(monkeypatch,key,value):
    monkeypatch.setattr(policy_module,key,value)
    with pytest.raises(ValueError): AppealPolicy.load(config(),TEST_DATABASE)


@pytest.mark.parametrize('settings,db',[(config(),'ap-students'),(config(False),TEST_DATABASE),
    (config(False),'unknown'),(config(False,application_id=5),'ap-students'),
    (config(False,guild_id=1),'ap-students')])
def test_safety(settings,db):
    with pytest.raises(ValueError): AppealPolicy.load(settings,db)


def test_prod_cannot_accelerate(monkeypatch):
    monkeypatch.setattr(policy_module,'PROD_REVIEW',300)
    monkeypatch.setattr(policy_module,'PROD_REMINDER',120)
    with pytest.raises(ValueError): AppealPolicy.load(config(False),'ap-students')


def test_deadline_stays_fixed_after_config_change(monkeypatch):
    old=AppealPolicy.load(config(),TEST_DATABASE)
    record={'submission_time':100, **old.snapshot(100)}
    monkeypatch.setattr(policy_module,'TEST_REVIEW',600)
    new=AppealPolicy.load(config(),TEST_DATABASE)
    assert new.review==600 and deadline(record)==400 and reminder_at(record)==280


def test_old_config_cannot_override_code_timers():
    c=config(ban_appeals={'testing':False,'review_duration_seconds':1})
    assert AppealPolicy.load(c,TEST_DATABASE).review==300
    assert AppealPolicy.load(config(False,ban_appeals={'testing':True,'review_duration_seconds':300}),'ap-students').review==PROD_REVIEW


def test_ping_role_priority_and_fallback():
    m=NS(id=4,name='Moderator'); c=NS(id=6,name='Chat Moderator')
    assert moderator_role(NS(id=1,roles=[c,m])) is m
    assert moderator_role(NS(id=1,roles=[c])) is c


@pytest.mark.parametrize('roles',[[],[NS(id=1,name='Moderator')],
    [NS(id=4,name='Moderator'),NS(id=5,name='Moderator')], [NS(id=4,name='Not a Moderator')]])
def test_bad_ping_roles(roles):
    with pytest.raises(RuntimeError): moderator_role(NS(id=1,roles=roles))


@pytest.mark.parametrize('name,admin,expected',[('Trial Chat Moderator',False,True),('Chat Moderator',False,True),
    ('Moderator',False,True),('Admin',False,True),('Lead Moderator',False,True),
    ('Not a Moderator',False,False),('Member',False,False),('Member',True,True)])
def test_voter_roles(name,admin,expected):
    assert eligible_voter(NS(roles=[NS(name=name)],guild_permissions=NS(administrator=admin)))==expected


def test_legacy_production_deadline():
    record={'submission_time':100,'decision':None}
    assert deadline(record)==100+PROD_REVIEW and reminder_at(record)==100+PROD_REVIEW-PROD_REMINDER


@pytest.mark.parametrize('now,votes,expected',[(279,0,False),(280,0,True),(280,3,True),(280,4,False),(399,3,True),(400,1,False)])
def test_reminder_boundary(now,votes,expected):
    record={'submission_time':100, **AppealPolicy.load(config(),TEST_DATABASE).snapshot(100)}
    assert reminder_due(record,now,votes)==expected


@pytest.mark.parametrize('key',['reminder_claimed_at','reminder_checked_at'])
def test_reminder_persistence(key):
    record={'submission_time':100, **AppealPolicy.load(config(),TEST_DATABASE).snapshot(100),key:280}
    assert not reminder_due(record,300,1)


def test_reappeal():
    assert reappeal_at({}) is None
    assert reappeal_at({'decision':True}) is None
    assert reappeal_at({'decision':False,'submission_time':400,'reappeal_at':700})==700
    assert reappeal_at({'decision':False,'submission_time':400})==400+PROD_COOLDOWN


@pytest.mark.parametrize('g,r,y,out',[({1},{2},set(),(False,2)),({1,2},{3},set(),(True,3)),
 (set(),set(),{1},(False,1)),(set(),set(),set(),(False,0)),({1},{1},{1},(False,1)),({1,2},{1},set(),(True,2))])
def test_vote_result(g,r,y,out): assert vote_result(g,r,y)==out


def test_history():
    record={'message_id':21,'channel_id':3,'decision':False,'previous_appeals':[{'message_id':i,'channel_id':3} for i in range(1,21)]}
    history=previous_appeals(record,3)
    assert len(history)==20 and history[-1]['message_id']==21 and history[0]['message_id']==2
    assert len(previous_appeals(dict(record,previous_appeals=history),3))==20


@pytest.mark.parametrize('sec,text',[(300,'5 minutes'),(1209600,'2 weeks'),(7257600,'12 weeks'),(1,'1 second')])
def test_display(sec,text): assert duration_text(sec)==text
