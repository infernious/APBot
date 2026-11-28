"""Evidence upload regressions using the existing Discord harness."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import nextcord
import pytest
from test_scam_image_detector import harness, BEAST
from cogs import scam_image_detector as cog

@pytest.fixture(autouse=True)
def file_double(monkeypatch):
    class File:
        def __init__(self, fp, *, filename):
            self.fp, self.filename = fp, filename
        def close(self): self.fp.close()
    monkeypatch.setattr(nextcord, 'File', File, raising=False)


def test_exact_evidence_uploaded_before_delete(harness):
    d,m,s,r,j = harness
    order = []
    async def send(**kwargs):
        if 'file' in kwargs:
            order.append('upload')
            assert 'embed' not in kwargs
            assert kwargs['file'].fp.read() == b'scamdata'
            assert kwargs['file'].filename == 'scam-7.png'
        else:
            order.append('embed')
            assert kwargs['embed'].title == 'Scam Detected'
            assert not getattr(getattr(kwargs['embed'], 'image', None), 'url', None)
        return NS(edit=AsyncMock())
    async def delete(): order.append('delete')
    r.send.side_effect = send; m.delete.side_effect = delete
    asyncio.run(d.process(j))
    assert order == ['upload', 'embed', 'delete']
    m.attachments[0].read.assert_awaited_once()
    assert r.send.call_args_list[0].kwargs['file'].fp.closed


def test_only_matching_attachment_uploaded(harness):
    d,m,s,r,j = harness
    clean = NS(id=6,filename='clean.png',size=5,content_type='image/png',read=AsyncMock(return_value=b'clean'))
    m.attachments.insert(0, clean)
    d.ocr.scan.side_effect = ['AP Biology', BEAST]
    async def send(**kwargs):
        if 'file' in kwargs:
            assert kwargs['file'].fp.read() == b'scamdata'
        return NS(edit=AsyncMock())
    r.send.side_effect = send
    asyncio.run(d.process(j)); m.delete.assert_awaited_once()


def test_failed_upload_prevents_deletion(harness):
    d,m,s,r,j = harness
    r.send.side_effect = RuntimeError('upload failed')
    with pytest.raises(RuntimeError): asyncio.run(d.process(j))
    m.delete.assert_not_called()
    assert r.send.call_args_list[0].kwargs['file'].fp.closed


def test_cached_match_still_uploads_actual_bytes(harness):
    d,m,s,r,j = harness
    async def send(**kwargs):
        if 'file' in kwargs:
            assert kwargs['file'].fp.read() == b'scamdata'
        return NS(edit=AsyncMock())
    r.send.side_effect = send
    async def run():
        await d.process(j); await d.process(j)
    asyncio.run(run()); d.ocr.scan.assert_awaited_once(); assert r.send.await_count == 4


def test_dry_run_does_not_upload(harness):
    d,m,s,r,j = harness; d.bot.config['scam_detector_dry_run'] = True
    asyncio.run(d.process(j)); r.send.assert_not_called(); m.delete.assert_not_called()


def test_final_embed_includes_count(harness):
    d,m,s,r,j = harness
    asyncio.run(d.process(j)); embed = r.send.return_value.edit.call_args.kwargs['embed']
    fields = { (x['name'] if isinstance(x,dict) else x.name): (x['value'] if isinstance(x,dict) else x.value) for x in embed.fields }
    assert fields['Messages Deleted'] == '1'; assert fields['Reason'] == 'Scam'
    assert 'Image SHA-256' not in fields
