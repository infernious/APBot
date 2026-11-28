"""Code defaults and standalone image evidence (no Discord network calls)."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from test_scam_image_detector import harness
from cogs import scam_image_detector as cog


def test_default_switches_production(harness):
    d, m, _, r, j = harness
    d.bot.config.pop('scam_detector_dry_run')
    assert d.config('scam_detector_enabled') is True
    assert d.config('scam_detector_dry_run') is True
    assert not d.test_mode()
    asyncio.run(d.process(j))
    r.send.assert_not_called()
    m.delete.assert_not_called()


def test_default_switches_test_bot(harness):
    d, m, _, r, _ = harness
    d.bot.user.id = cog.TEST_BOT_ID
    d.bot.config.update(application_id=cog.TEST_BOT_ID, guild_id=cog.TEST_GUILD_ID)
    d.bot.config.pop('scam_detector_dry_run')
    m.guild.id = cog.TEST_GUILD_ID
    m.guild.me.id = cog.TEST_BOT_ID
    m.author.guild_permissions.administrator = True
    r.permissions_for = lambda who: NS(view_channel=who is m.guild.me, send_messages=True, embed_links=True, attach_files=True)
    assert d.test_mode() and d.eligible(m)
    assert not d.in_scope(1, 2)
    asyncio.run(d.process(cog.Job(cog.TEST_GUILD_ID, 2, 7, 0)))
    assert r.send.await_count == 2
    assert 'files' in r.send.call_args_list[0].kwargs and 'embed' not in r.send.call_args_list[0].kwargs
    assert 'embed' in r.send.call_args_list[1].kwargs and 'files' not in r.send.call_args_list[1].kwargs
    m.delete.assert_not_called()


def test_switch_can_disable_scanning(harness, monkeypatch):
    d, m, _, r, j = harness
    monkeypatch.setattr(cog, 'SCAM_DETECTOR_ENABLED', False)
    asyncio.run(d.process(j))
    r.send.assert_not_called(); m.delete.assert_not_called()


def test_evidence_link_and_log_order(harness):
    d, m, _, r, j = harness
    evidence_url = 'https://discord.com/channels/1/8/123'
    audit = NS(edit=AsyncMock())
    r.send.side_effect = [NS(jump_url=evidence_url), audit]
    asyncio.run(d.process(j))
    first, second = [c.kwargs for c in r.send.call_args_list]
    assert 'file' in first and 'embed' not in first
    assert 'embed' in second and 'file' not in second
    fields = second['embed'].fields
    assert any(evidence_url in (f['value'] if isinstance(f, dict) else f.value) for f in fields)
    m.delete.assert_awaited_once()
    audit.edit.assert_awaited_once()


def test_failed_embed_send_prevents_punishment(harness):
    d, m, _, r, j = harness
    m.author.timeout = AsyncMock()
    r.send.side_effect = [NS(), RuntimeError('log send failed')]
    with pytest.raises(RuntimeError):
        asyncio.run(d.process(j))
    m.delete.assert_not_called(); m.author.timeout.assert_not_called()
