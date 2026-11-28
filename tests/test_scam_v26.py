"""Name-based destination and role resolution; no Discord network calls."""
import asyncio
from types import SimpleNamespace as NS
import pytest
from test_scam_image_detector import harness, Role, TextChannel
from cogs import scam_image_detector as cog

@pytest.mark.parametrize('name', ['Admin','Moderator','Chat Moderator','Lead Moderator','Trial Chat Moderator','mOdErAtOr'])
def test_staff_names(harness,name):
    d,m,s,r,j=harness
    m.author.roles=[Role(555,name)]
    assert cog.staff(m.author)
    asyncio.run(d.process(j)); m.delete.assert_not_called()

@pytest.mark.parametrize('name', ['Moderator Fan','Admin Club','Not Moderator','Badminton Club'])
def test_no_substring_bypass(harness,name):
    d,m,s,r,j=harness
    m.author.roles=[Role(555,name)]
    assert not cog.staff(m.author)

def test_named_log_and_ignore_stale_config(harness):
    d,m,s,r,j=harness
    d.bot.config['scam_detector_review_channel_id']=999999
    r.id=99; r.name='Automod-Bot'
    assert d.private_review(m.guild) is r
    asyncio.run(d.process(j)); m.delete.assert_awaited_once()
    assert not d.in_scope(m.guild.id,r.id)

@pytest.mark.parametrize('kind',['missing','duplicate','foreign','no_attach','ordinary_role'])
def test_unsafe_destination(harness,kind):
    d,m,s,r,j=harness
    if kind=='missing': r.name='other'
    elif kind=='duplicate':
        other=TextChannel(); other.guild=m.guild; other.name='automod-bot'; other.id=55
        m.guild.text_channels.append(other)
    elif kind=='foreign': r.guild=NS(id=999)
    elif kind=='no_attach':
        r.permissions_for=lambda who:NS(view_channel=who is m.guild.me,send_messages=True,embed_links=True,attach_files=False)
    else:
        r.permissions_for=lambda who:NS(view_channel=who is not m.guild.default_role,send_messages=True,embed_links=True,attach_files=True)
    assert d.private_review(m.guild) is None
    asyncio.run(d.process(j)); m.delete.assert_not_called(); r.send.assert_not_called()

def test_named_staff_role_may_view_log(harness):
    d,m,s,r,j=harness
    mod=Role(42,'Moderator'); m.guild.roles.append(mod)
    r.permissions_for=lambda who:NS(view_channel=who is m.guild.me or who is mod,send_messages=True,embed_links=True,attach_files=True)
    assert d.private_review(m.guild) is r
