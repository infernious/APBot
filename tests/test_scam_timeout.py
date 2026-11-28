"""Regression coverage for the seven-day scam timeout; no Discord network calls."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
import nextcord
from cogs import scam_image_detector as cog
from test_scam_image_detector import harness, Member

@pytest.fixture
def timeout_harness(harness):
    d, m, s, r, j = harness
    guild = m.guild
    guild.owner_id = 100
    guild.me.guild_permissions.moderate_members = True
    guild.me.top_role = 10
    m.author.top_role = 1
    m.author.communication_disabled_until = None
    m.author.timeout = AsyncMock()
    m.author.ban = AsyncMock()
    guild.fetch_member = AsyncMock(return_value=m.author)
    guild.ban = AsyncMock()
    return harness


def outcome(r):
    for field in r.send.return_value.edit.call_args.kwargs['embed'].fields:
        name = field['name'] if isinstance(field, dict) else field.name
        if name == 'Timeout':
            return field['value'] if isinstance(field, dict) else field.value
    raise AssertionError('Missing timeout audit result')


def test_delete_then_timeout(timeout_harness):
    d,m,s,r,j = timeout_harness
    order = []
    async def deleted(): order.append('delete')
    async def muted(**kwargs): order.append('timeout')
    m.delete.side_effect = deleted
    m.author.timeout.side_effect = muted
    before = datetime.now(timezone.utc)
    asyncio.run(d.process(j))
    after = datetime.now(timezone.utc)
    assert order == ['delete','timeout']
    args = m.author.timeout.call_args.kwargs
    assert args['reason'] == 'Scam'
    assert before + timedelta(days=7) <= args['timeout'] <= after + timedelta(days=7)
    assert 'Applied 7-day' in outcome(r)
    m.author.ban.assert_not_called(); m.guild.ban.assert_not_called()


@pytest.mark.parametrize('mode', ['dry', 'default', 'report', 'staff', 'no_image', 'clean', 'changed', 'no_audit'])
def test_no_timeout_without_confirmed_enforcement(timeout_harness, mode):
    d,m,s,r,j = timeout_harness
    if mode == 'dry': d.bot.config['scam_detector_dry_run'] = True
    if mode == 'default': d.bot.config.pop('scam_detector_dry_run')
    if mode == 'report': m.content = 'Is this a scam?'
    if mode == 'staff': m.author.guild_permissions.administrator = True
    if mode == 'no_image': m.attachments = []
    if mode == 'clean': d.ocr.scan.return_value = 'AP Biology'
    if mode == 'changed': s.fetch_message.side_effect = [m, NS(**{**vars(m), 'attachments': []})]
    if mode == 'no_audit': r.permissions_for = lambda who: NS(view_channel=True)
    asyncio.run(d.process(j))
    m.author.timeout.assert_not_called(); m.delete.assert_not_called(); m.guild.fetch_member.assert_not_called()


@pytest.mark.parametrize('days', [7, 10, 28])
def test_existing_timeout_preserved(timeout_harness, days):
    d,m,s,r,j = timeout_harness
    m.author.communication_disabled_until = datetime.now(timezone.utc) + timedelta(days=days)
    asyncio.run(d.process(j))
    m.delete.assert_awaited_once(); m.author.timeout.assert_not_called(); assert 'Preserved' in outcome(r)


def test_shorter_timeout_extended(timeout_harness):
    d,m,s,r,j = timeout_harness
    m.author.communication_disabled_until = datetime.now(timezone.utc) + timedelta(days=1)
    asyncio.run(d.process(j)); m.author.timeout.assert_awaited_once()


@pytest.mark.parametrize('mode', ['permission', 'hierarchy', 'owner', 'promoted', 'missing', 'fetch_timeout', 'disabled_after_delete'])
def test_timeout_safety(timeout_harness, mode):
    d,m,s,r,j = timeout_harness
    if mode == 'permission': m.guild.me.guild_permissions.moderate_members = False
    if mode == 'hierarchy': m.author.top_role = 10
    if mode == 'owner': m.guild.owner_id = m.author.id
    if mode == 'promoted':
        promoted = Member(True); m.guild.fetch_member.return_value = promoted
    if mode == 'missing': m.guild.fetch_member.side_effect = nextcord.NotFound(NS(status=404, reason='Not Found'), 'Unknown Member')
    if mode == 'fetch_timeout': m.guild.fetch_member.side_effect = asyncio.TimeoutError()
    if mode == 'disabled_after_delete':
        async def disable(): d.bot.config['scam_detector_dry_run'] = True
        m.delete.side_effect = disable
    asyncio.run(d.process(j)); m.delete.assert_awaited_once(); m.author.timeout.assert_not_called()
    assert 'Skipped' in outcome(r) or 'Failed' in outcome(r)


def test_failed_delete_no_timeout(timeout_harness):
    d,m,s,r,j = timeout_harness
    m.delete.side_effect = asyncio.TimeoutError()
    asyncio.run(d.process(j)); m.author.timeout.assert_not_called(); assert 'Not attempted' in outcome(r)


def test_timeout_failure_logged_separately(timeout_harness):
    d,m,s,r,j = timeout_harness
    m.author.timeout.side_effect = asyncio.TimeoutError()
    asyncio.run(d.process(j)); m.delete.assert_awaited_once(); assert 'Failed or unconfirmed' in outcome(r)
    assert r.send.return_value.edit.call_args.kwargs['embed'].description == 'Removed by APBot'


def test_repeated_scan_does_not_extend(timeout_harness):
    d,m,s,r,j = timeout_harness
    async def set_timeout(*,timeout,reason): m.author.communication_disabled_until=timeout
    m.author.timeout.side_effect = set_timeout
    async def run():
        await d.process(j); await d.process(j)
    asyncio.run(run()); assert m.delete.await_count == 2; m.author.timeout.assert_awaited_once()
