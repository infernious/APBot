"""Offline service tests. Discord/Mongo operations are mocked; not a live integration test."""
import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
import sys
import pytest
from test_appeal_policy import config, AppealPolicy, TEST_DATABASE, mock_test_identity


@pytest.fixture
def mod(monkeypatch):
    nc=ModuleType('nextcord'); ext=ModuleType('nextcord.ext')
    class Dummy:
        def __init__(self,*a,**k): self.__dict__.update(k)
        def add_field(self,**k): self.__dict__.setdefault("fields", []).append(k)
    class NotFound(Exception):
        def __init__(self,code): self.code=code
    nc.NotFound=NotFound
    nc.Embed=nc.Object=nc.Interaction=Dummy
    nc.AllowedMentions=type('Mentions',(Dummy,),{'none':staticmethod(lambda:None)})
    nc.ButtonStyle=NS(blurple=1,gray=2);nc.TextInputStyle=NS(paragraph=1)
    nc.ui=NS(Modal=Dummy,View=Dummy,Button=Dummy,TextInput=Dummy,button=lambda **kw:lambda f:f)
    nc.slash_command=lambda **kw:lambda f:f
    ext.commands=NS(Cog=Dummy)
    for name,value in {'nextcord':nc,'nextcord.ext':ext,'bot_base':NS(APBot=Dummy),'config_handler':NS(Config=lambda p:config())}.items():
        monkeypatch.setitem(sys.modules,name,value)
    path=Path(__file__).resolve().parents[1]/'src/cogs/moderation/appeal.py'
    spec=importlib.util.spec_from_file_location('_appeal_test_module',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def service(mod, **fields):
    p=AppealPolicy.load(config(),TEST_DATABASE)
    record={'user_id':9,'message_id':10,'guild_id':1,'channel_id':3,'decision':None,'submission_time':100,**p.snapshot(100),**fields}
    collection=NS(find_one=AsyncMock(side_effect=lambda q:dict(record)),update_one=AsyncMock())
    async def update(q,change,**kwargs):
        if q.get('message_id',10)!=record.get('message_id') or ("decision" in q and record.get('decision') is not q['decision']):
            return NS(modified_count=0)
        record.update(change.get('$set',{}))
        for k,v in change.get('$inc',{}).items():record[k]=record.get(k,0)+v
        for k in change.get('$unset',{}):record.pop(k,None)
        return NS(modified_count=1)
    collection.update_one.side_effect=update
    dm=NS(send=AsyncMock());bot=NS(config=config(),db=NS(appeal=NS(ban_appeals=collection,database=NS(name=TEST_DATABASE))),user=NS(id=5),colors={'green':1,'red':2,'light_orange':3},getch_user=AsyncMock(return_value=dm))
    s=mod.AppealService(bot)
    thread=NS(id=10,locked=False,parent_id=3,send=AsyncMock(),edit=AsyncMock())
    message=NS(id=10,author=NS(id=5),thread=thread,reactions=[])
    guild=NS(unban=AsyncMock());channel=NS(id=3,fetch_message=AsyncMock(return_value=message));role=NS(mention='<@&4>')
    s.environment=AsyncMock(return_value=(guild,channel,role));s.current_ban=AsyncMock(return_value=NS(reason='test'))
    s.ballots=AsyncMock(return_value=(False,0))
    return s,record,thread,guild,channel,dm


def run(coro):return asyncio.run(coro)


def test_early_no_action(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:279)
    run(s.process(9,10));c.fetch_message.assert_not_called();g.unban.assert_not_called()


def test_reminder_once_after_restart(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:280)
    s.ballots.return_value=(True,3)
    async def exercise():
        await s.process(9,10)
        restarted=mod.AppealService(s.bot)
        restarted.environment=s.environment;restarted.ballots=s.ballots
        await restarted.process(9,10)
    run(exercise());assert t.send.await_count==1 and r['reminder_claimed_at']==280
    g.unban.assert_not_called()


def test_no_reminder_four_voters(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:280);s.ballots.return_value=(True,4)
    run(s.process(9,10));t.send.assert_not_called();assert r['reminder_checked_at']==280


def test_denied_and_cooldown(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:400)
    async def exercise():await s.process(9,10);await s.process(9,10)
    run(exercise());assert r['decision'] is False and r['reappeal_at']==700
    assert d.send.await_count==1;g.unban.assert_not_called();t.edit.assert_awaited_once()


def test_accepted_once(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:400);s.ballots.return_value=(True,2)
    async def exercise():await s.process(9,10);await s.process(9,10)
    run(exercise());assert r['decision'] is True;g.unban.assert_awaited_once();d.send.assert_awaited_once()


def test_manual_unban(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:400);s.current_ban.return_value=None
    run(s.process(9,10));assert r['decision'] is True;g.unban.assert_not_called();d.send.assert_not_called()


def test_unknown_ban_race(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:400);s.ballots.return_value=(True,1);g.unban.side_effect=mod.nextcord.NotFound(10026)
    run(s.process(9,10));assert r['decision'] is True;d.send.assert_not_called()


def test_missing_message_hold(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:400);c.fetch_message.side_effect=mod.nextcord.NotFound(10008)
    run(s.process(9,10));assert r['decision'] is None and r['hold_reason'];g.unban.assert_not_called()


def test_update_no_deadline_reset(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:200)
    inter=NS(guild_id=2,user=NS(id=9));out=run(s.add_information(inter,10,'My additional information'))
    assert 'original deadline' in out and r['deadline_at']==400 and r['submission_time']==100 and r['updates_count']==1
    t.send.assert_awaited_once()


@pytest.mark.parametrize('fields,mid,now', [({'updates_count':5},10,200),({'last_update_at':190},10,200),({},11,200),({},10,400),({'decision':False},10,200)])
def test_update_refused(mod,monkeypatch,fields,mid,now):
    s,r,t,g,c,d=service(mod,**fields);monkeypatch.setattr(mod.time,'time',lambda:now)
    run(s.add_information(NS(guild_id=2,user=NS(id=9)),mid,'An additional statement'))
    t.send.assert_not_called()


def test_non_banned_cannot_appeal(mod):
    s,r,t,g,c,d=service(mod);s.current_ban.return_value=None
    out=run(s.submit(NS(guild_id=2,user=NS(id=9)),'appeal','',''))
    assert 'not currently banned' in out;s.collection.update_one.assert_not_called()


def test_duplicate_active_submission(mod):
    s,r,t,g,c,d=service(mod)
    out=run(s.submit(NS(guild_id=2,user=NS(id=9)),'appeal','',''))
    assert 'still being considered' in out;s.collection.update_one.assert_not_called()


def test_reappeal_blocked_until_cooldown(mod,monkeypatch):
    s,r,t,g,c,d=service(mod,decision=False,reappeal_at=700);monkeypatch.setattr(mod.time,'time',lambda:699)
    out=run(s.submit(NS(guild_id=2,user=NS(id=9)),'appeal','',''))
    assert '700' in out;s.collection.update_one.assert_not_called()


def test_wrong_environment(mod,monkeypatch):
    s,r,t,g,c,d=service(mod,guild_id=99);monkeypatch.setattr(mod.time,'time',lambda:400)
    run(s.process(9,10));s.environment.assert_not_called()


def test_changed_ban_reason_holds(mod,monkeypatch):
    s,r,t,g,c,d=service(mod,ban_fingerprint=mod.ban_fingerprint(NS(reason='older ban')))
    monkeypatch.setattr(mod.time,'time',lambda:400);s.ballots.return_value=(True,3)
    run(s.process(9,10));assert r['decision'] is None and 'changed' in r['hold_reason'];g.unban.assert_not_called()


def test_reappeal_at_boundary_creates_new_deadline(mod,monkeypatch):
    s,r,t,g,c,d=service(mod,decision=False,reappeal_at=700)
    monkeypatch.setattr(mod.time,'time',lambda:700)
    new=NS(id=11,add_reaction=AsyncMock(),create_thread=AsyncMock(return_value=NS(id=11)))
    c.send=AsyncMock(return_value=new);s.history=AsyncMock()
    result=run(s.submit(NS(guild_id=2,user=NS(id=9,name='Example')), 'A valid appeal statement', '', ''))
    assert '1000' in result and r['deadline_at']==1000 and r['reminder_at']==880
    assert r['decision'] is None and r['message_id']==11 and r['previous_appeals'][-1]['message_id']==10
    assert 'reappeal_at' not in r


@pytest.mark.parametrize('bot_id,private,appeal_present,expected',[(5,True,True,True),
    (99,True,True,False),(5,False,True,False),(5,True,False,False)])
def test_real_environment_checks(mod,bot_id,private,appeal_present,expected):
    role=NS(id=4,name='Moderator')
    guild=NS(id=1,roles=[role],default_role=NS(id=1))
    channel=NS(guild=guild,permissions_for=lambda r:NS(view_channel=not private))
    bot=NS(config=config(),db=NS(appeal=NS(ban_appeals=None,database=NS(name=TEST_DATABASE))),
        user=NS(id=bot_id),get_guild=lambda i:guild if i==1 else (NS(id=2) if appeal_present else None),
        getch_channel=AsyncMock(return_value=channel))
    svc=mod.AppealService(bot)
    if expected:
        assert run(svc.environment())==(guild,channel,role)
    else:
        with pytest.raises(RuntimeError):run(svc.environment())


def test_update_matches_appeal_embed(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:200)
    run(s.add_information(NS(guild_id=2,user=NS(id=9)),10,'Additional details'))
    emb=t.send.await_args.kwargs['embed']
    assert emb.title=='Ban Appeal Update' and emb.color==3
    assert [f['name'] for f in emb.fields]==['User Info','Additional Information','Decision deadline']
    assert emb.fields[1]['value']=='```\nAdditional details\n```' and '<t:400:F>' in emb.fields[2]['value']

@pytest.mark.parametrize('voters,phrase',[(0,'No staff members'),(1,'Only **1 staff member** has voted'),(3,'Only **3 staff members** have voted')])
def test_human_reminder(mod,monkeypatch,voters,phrase):
    s,r,t,g,c,d=service(mod);monkeypatch.setattr(mod.time,'time',lambda:280)
    s.ballots.return_value=(False,voters)
    run(s.process(9,10))
    content=t.send.await_args.args[0]
    assert phrase in content and 'closes <t:400:R>' in content and '<@&4>' in content


def test_history_uses_warning_cog_and_retains_links(mod):
    s,r,t,g,c,d=service(mod)
    warnings=NS(post_appeal_warnings=AsyncMock()); s.bot.get_cog=Mock(return_value=warnings); s.bot.get_guild=Mock(return_value=g)
    run(s.history(t,9,[{'channel_id':3,'message_id':7,'decision':False}]))
    warnings.post_appeal_warnings.assert_awaited_once_with(t,9,g)
    assert 'https://discord.com/channels/1/3/7' in t.send.await_args_list[0].kwargs['embed'].description


def test_history_failure_preserves_links(mod):
    s,r,t,g,c,d=service(mod);s.bot.get_cog=Mock(return_value=None)
    run(s.history(t,9,[{'channel_id':3,'message_id':7,'decision':False}]))
    assert t.send.await_count==2 and '/warnings' in t.send.await_args.args[0]


@pytest.fixture
def warning_cog(mod,monkeypatch):
    nc=mod.nextcord
    for name in ('Permissions','Member','TextChannel','SlashOption'):
        monkeypatch.setattr(nc,name,nc.Embed,raising=False)
    monkeypatch.setattr(nc,'Color',NS(**{name:lambda:123 for name in ('yellow','orange','red','green','purple','gold')}),raising=False)
    monkeypatch.setattr(nc.Embed,'set_image',lambda self,**kw:setattr(self,'image',kw),raising=False)
    monkeypatch.setitem(sys.modules,'app_config',NS(get_command_guild_ids=lambda c:[],load_optional_config=lambda:{}))
    path=Path(__file__).resolve().parents[1]/'src/cogs/moderation/infraction.py'
    spec=importlib.util.spec_from_file_location('_warning_test_module',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    db=NS(get_user_infractions=AsyncMock(),get_inf_points=AsyncMock(return_value=0))
    cog=module.Infraction(NS(db=NS(base_db=db),colors={'red':2}))
    cog.resolve_moderator=AsyncMock(return_value=(NS(mention='<@123>',display_name='Example Mod'),123))
    return cog,db


def infraction(reason='test'):
    from datetime import datetime,timezone
    return NS(actiontype='ban',reason=reason,moderator=123,actiontime=datetime(2026,11,26,21,49,tzinfo=timezone.utc),duration=None,attachment_url=None,update=[])


def test_standard_warning_embed(warning_cog):
    cog,db=warning_cog;db.get_user_infractions.return_value=[infraction()]
    thread=NS(send=AsyncMock());guild=NS(id=1)
    run(cog.post_appeal_warnings(thread,9,guild))
    assert thread.send.await_count==2
    assert 'Showing all 1' in thread.send.await_args_list[0].args[0]
    emb=thread.send.await_args.kwargs['embed']
    assert emb.title=='#1 - Ban' and emb.color==2
    assert 'Reason: test' in emb.description and 'Responsible Mod: <@123> (Example Mod)' in emb.description and '1/1 infractions' in emb.description
    db.get_user_infractions.assert_awaited_once_with(9);db.get_inf_points.assert_awaited_once_with(9)
    assert all('allowed_mentions' in c.kwargs for c in thread.send.await_args_list)


def test_large_warning_history_bounded(warning_cog):
    cog,db=warning_cog;db.get_user_infractions.return_value=[infraction(str(i)) for i in range(55)]
    thread=NS(send=AsyncMock());run(cog.post_appeal_warnings(thread,9,None))
    assert thread.send.await_count==51
    assert 'latest 50 of 55' in thread.send.await_args_list[0].args[0]
    assert thread.send.await_args_list[1].kwargs['embed'].title=='#6 - Ban'
    assert thread.send.await_args.kwargs['embed'].title=='#55 - Ban'


def test_no_warning_history(warning_cog):
    cog,db=warning_cog;db.get_user_infractions.return_value=[];db.get_inf_points.return_value=None
    thread=NS(send=AsyncMock());run(cog.post_appeal_warnings(thread,9,None))
    assert thread.send.await_count==1 and 'No recorded infractions' in thread.send.await_args.args[0] and 'unavailable' in thread.send.await_args.args[0]


@pytest.mark.parametrize('fields,now,banned,guild_id,expected', [
    ({'decision':False,'reappeal_at':700},699,True,2,'700'),
    ({'decision':False,'reappeal_at':700},700,True,2,None),
    ({'decision':False,'reappeal_at':700},900,True,2,None),
    ({'decision':False,'reappeal_at':700},699,False,2,'not currently banned'),
    ({},200,True,2,'still being considered'),
    ({'decision':True},200,True,2,None),
    ({'guild_id':99},200,True,2,'different environment'),
    ({},200,True,99,'configured appeal server'),
])
def test_appeal_button_preflight(mod,monkeypatch,fields,now,banned,guild_id,expected):
    s,r,t,g,c,d=service(mod,**fields)
    monkeypatch.setattr(mod.time,'time',lambda:now)
    if not banned:s.current_ban.return_value=None
    factory=Mock(return_value=object());monkeypatch.setattr(mod,'BanAppealModal',factory)
    response=NS(send_message=AsyncMock(),send_modal=AsyncMock(),is_done=lambda:False)
    inter=NS(guild_id=guild_id,user=NS(id=9),response=response)
    run(mod.BanAppealView(s).callback(None,inter))
    if expected is not None:
        response.send_message.assert_awaited_once()
        assert expected in response.send_message.await_args.args[0]
        assert response.send_message.await_args.kwargs['ephemeral'] is True
        response.send_modal.assert_not_called();factory.assert_not_called()
    else:
        factory.assert_called_once_with(s)
        response.send_modal.assert_awaited_once_with(factory.return_value)
        response.send_message.assert_not_called()
    s.collection.update_one.assert_not_called();t.send.assert_not_called();d.send.assert_not_called()


def test_first_appeal_button_opens(mod,monkeypatch):
    s,r,t,g,c,d=service(mod);s.collection.find_one.side_effect=None;s.collection.find_one.return_value=None
    factory=Mock(return_value=object());monkeypatch.setattr(mod,'BanAppealModal',factory)
    response=NS(send_message=AsyncMock(),send_modal=AsyncMock(),is_done=lambda:False)
    run(mod.BanAppealView(s).callback(None,NS(guild_id=2,user=NS(id=9),response=response)))
    response.send_modal.assert_awaited_once_with(factory.return_value)
    s.collection.update_one.assert_not_called()


@pytest.mark.parametrize('error,expected',[(RuntimeError('DB unavailable'),'Could not check'),(asyncio.TimeoutError(),'in time')])
def test_preflight_fail_closed(mod,monkeypatch,error,expected):
    s,r,t,g,c,d=service(mod);s.collection.find_one.side_effect=error
    factory=Mock();monkeypatch.setattr(mod,'BanAppealModal',factory)
    response=NS(send_message=AsyncMock(),send_modal=AsyncMock(),is_done=lambda:False)
    run(mod.BanAppealView(s).callback(None,NS(guild_id=2,user=NS(id=9),response=response)))
    assert expected in response.send_message.await_args.args[0]
    assert response.send_message.await_args.kwargs['ephemeral'] is True
    response.send_modal.assert_not_called();factory.assert_not_called();s.collection.update_one.assert_not_called()


def test_preflight_does_not_authorize_stale_modal(mod,monkeypatch):
    s,r,t,g,c,d=service(mod,decision=False,reappeal_at=700);monkeypatch.setattr(mod.time,'time',lambda:700)
    inter=NS(guild_id=2,user=NS(id=9))
    assert run(s.submission_preflight(inter)) is None
    r['decision']=None  # Another submission occurred while this modal was open.
    assert 'still being considered' in run(s.submit(inter,'A valid appeal statement','',''))
    s.collection.update_one.assert_not_called()


@pytest.mark.parametrize('value,limit', [('Normal text with **markdown** and https://example.com',750),
    ('a'*750,750),('a'*1000,1000),('```\n@everyone\n```',1000),('`'*1000,1000),('```````',750)])
def test_appeal_text_code_block(mod,value,limit):
    result=mod.appeal_code_block(value,limit)
    assert result.startswith('```\n') and result.endswith('\n```')
    assert len(result)<=1024 and '```' not in result[4:-4]
    if '`' not in value:
        assert result[4:-4]==value


def test_original_appeal_body_style_only(mod,monkeypatch):
    s,r,t,g,c,d=service(mod,decision=False,reappeal_at=700)
    monkeypatch.setattr(mod.time,'time',lambda:700)
    new=NS(id=11,add_reaction=AsyncMock(),create_thread=AsyncMock(return_value=NS(id=11)))
    c.send=AsyncMock(return_value=new);s.history=AsyncMock()
    run(s.submit(NS(guild_id=2,user=NS(id=9,name='Example')), 'My original appeal\n**text**', 'https://example.com', 'Other details'))
    emb=c.send.await_args.kwargs['embed']
    assert emb.title=='Ban Appeal' and emb.color==3
    assert [f['name'] for f in emb.fields]==['User Info','Ban Appeal','Supporting Media','Additional Information','Decision deadline']
    assert emb.fields[1]['value']=='```\nMy original appeal\n**text**\n```'
    assert emb.fields[2]['value']=='```\nhttps://example.com\n```'
    assert emb.fields[3]['value']=='```\nOther details\n```'
    assert '<t:1000:F>' in emb.fields[4]['value'] and r['deadline_at']==1000



def history_embed(mod, prior):
    s,r,t,g,c,d=service(mod)
    warnings=NS(post_appeal_warnings=AsyncMock())
    s.bot.get_cog=Mock(return_value=warnings);s.bot.get_guild=Mock(return_value=g)
    run(s.history(t,9,prior))
    warnings.post_appeal_warnings.assert_awaited_once_with(t,9,g)
    assert t.send.await_count==1
    return t.send.await_args.kwargs['embed']


def history_row(timestamp, decision, channel_id=3):
    return {'channel_id':channel_id,'message_id':((timestamp*1000-1420070400000)<<22)+1,'decision':decision}


def test_previous_appeals_single(mod):
    row=history_row(1795740000,False)
    emb=history_embed(mod,[row])
    assert emb.title=='Previous Appeals' and emb.color==3
    assert '1 previous appeal on record.' in emb.description
    assert '**#1 • 🔴 Rejected**' in emb.description
    assert 'Submitted: <t:1795740000:D>' in emb.description
    assert f"[View previous appeal](https://discord.com/channels/1/3/{row['message_id']})" in emb.description


def test_previous_appeals_newest_first(mod):
    rows=[history_row(1795740000,True),history_row(1795740200,None),history_row(1795740100,False)]
    desc=history_embed(mod,rows).description
    assert '3 previous appeals on record.' in desc
    assert desc.index('**#3 • ⚪ Closed/unknown**') < desc.index('**#2 • 🔴 Rejected**') < desc.index('**#1 • 🟢 Accepted**')


def test_previous_appeals_cap(mod):
    desc=history_embed(mod,[history_row(1795740000+i,False) for i in range(20)]).description
    assert '20 previous appeals on record.' in desc
    assert desc.count('[View previous appeal]')==8 and '+12 older appeals not shown' in desc
    assert '**#20' in desc and '**#13' in desc and len(desc)<4096


def test_previous_appeals_filters_and_deduplicates(mod):
    row=history_row(1795740000,True)
    desc=history_embed(mod,[row,dict(row),history_row(1795740100,False,99),{'channel_id':3,'message_id':'bad'}, {'channel_id':3,'message_id':0},{'channel_id':3,'message_id':True},{'channel_id':3,'message_id':2**64}]).description
    assert '1 previous appeal on record.' in desc and desc.count('[View previous appeal]')==1


def test_previous_appeals_empty(mod):
    emb=history_embed(mod,[history_row(1795740000,False,99)])
    assert emb.description=='No previous appeals recorded by this system.'
