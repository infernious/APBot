"""Narrow detector contract; old broad-score expectations intentionally retired."""
import asyncio
import hashlib
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
import nextcord
from cogs import scam_image_detector as cog
from utils import scam_rules as rules

TRUMP = "Donald J. Trump I'm excited to announce the launch of my very own crypto casino! To celebrate, I'm giving away $5,600 to everyone who registers and you can withdraw the bonus instantly. How to claim your reward: Go to vanowin.com. Enter the special promo code: USA. Receive your $5,600 bonus. This post will be deleted one hour after publication."
BEAST = "MrBeast I am pleased to announce the launch of my own cryptocurrency casino linked to the Vyro project. I am giving away $3,500 to everyone who registers, and you can withdraw the bonus immediately. How to claim your reward: Go to pusawin.com. Enter the special promo code: CASH."
PAYOUT = 'pusawin.com/profile/withdraw Withdrawal Success! Your Withdrawal of $3700.00 Was Successfully! The money will be transferred to your specified wallet.'
BONUS = 'vanowin.com/profile/bonuses Activate Code for Bonus Enter the promo code and receive an exclusive reward'

@pytest.mark.parametrize('text', [TRUMP, BEAST, PAYOUT, BONUS, BEAST.replace('pusawin.com', 'example.net'), TRUMP.replace('vanowin.com','example.org'), BEAST.upper(), BEAST.replace('MrBeast','Mr Beast'), BEAST.replace('promo code','promo\ncode')])
def test_campaign_matches(text):
    assert rules.classify_image_text(text).delete

@pytest.mark.parametrize('text', ['MrBeast meme', 'Mr Beast gives away $500 visit example.org', 'I bought $5600 of bitcoin', 'Stock price USD 53.20', 'Withdrawal Success! $3700 USDC wallet', 'Withdrawal Success! $3700 USDC wallet example.org', 'MrBeast crypto casino news', 'MrBeast casino $500 bonus register example.org', 'MrBeast crypto casino $500 bonus register example.org', 'I won $500 on crypto casino example.org', 'pusawin.com', 'vanowin.com review', 'AP Chemistry', 'free nitro claim https://discord.gift/example', 'Donald Trump announcement', 'Here is the video x.com/mrbeast', 'MrBeast cryptocurrency casino $500 free register x.com promo code withdraw instantly', 'NSFW screenshot', 'QR code', '', None, 'https://evilpusawin.com withdrawal success $5600 wallet', 'pusawin.com.evil.example withdrawal success $5600 wallet'])
def test_unrelated_remains(text):
    assert rules.classify_image_text(text) is None

@pytest.mark.parametrize('caption', ['Is this a scam?', 'Scam warning', 'Do not click', 'This is a scam', 'Reporting a scam'])
def test_reporting_context(caption):
    assert rules.report_context(caption)
    assert rules.classify_image_text(caption+' '+BEAST).delete is False

@pytest.mark.parametrize('name,mime,size,expected', [('a.png','image/png',100,True), ('a.jpg',None,100,True),('a.webp','image/webp',100,True),('a.mp4','video/mp4',100,False),('a.gif','image/gif',100,False),('a.png','text/plain',100,False),('a.png','image/png',cog.MAX_SCAN_BYTES+1,False),('a.png','image/png',0,False)])
def test_media_scope(name,mime,size,expected):
    assert cog.is_visual_attachment(NS(filename=name,content_type=mime,size=size)) is expected

class Member:
    def __init__(self, staff=False):
        self.id=3; self.bot=False; self.roles=[]; self.guild_permissions=NS(administrator=staff,manage_messages=False)

class Role:
    def __init__(self, id, name='ordinary', admin=False, manage=False):
        self.id=id; self.name=name; self.permissions=NS(administrator=admin,manage_messages=manage)
    def is_bot_managed(self): return False

class TextChannel:
    pass

@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setattr(nextcord,'Member',Member)
    monkeypatch.setattr(nextcord,'Role',Role)
    monkeypatch.setattr(nextcord,'TextChannel',TextChannel)
    bot=NS(user=NS(id=99),config={'application_id':99,'guild_id':1,'scam_detector_dry_run':False})
    every=Role(1); ordinary=Role(4); me=Member(True); me.id=99
    guild=NS(id=1,default_role=every,roles=[every,ordinary],me=me)
    source=NS(id=2,guild=guild)
    review=TextChannel(); review.id=8; review.name='automod-bot'; review.guild=guild; review.overwrites={}; review.send=AsyncMock(return_value=NS(edit=AsyncMock()))
    review.permissions_for=lambda who: NS(view_channel=who is me,send_messages=True,embed_links=True,attach_files=True)
    guild.text_channels=[review]
    bot.get_channel=lambda id: source if id==2 else review if id==review.id else None
    detector=cog.ScamImageDetector(bot)
    image = NS(id=5,filename='a.png',size=8,content_type='image/png',read=AsyncMock(return_value=b'scamdata'))
    detector.ocr.scan=AsyncMock(return_value=BEAST)
    message=NS(id=7,guild=guild,channel=source,author=Member(),content='',attachments=[image],delete=AsyncMock())
    source.fetch_message=AsyncMock(return_value=message)
    job=cog.Job(1,2,7,0)
    return detector,message,source,review,job


def test_delete_and_audit(harness):
    d,m,s,r,j=harness
    asyncio.run(d.process(j)); m.delete.assert_awaited_once(); assert r.send.await_count == 2
    assert r.send.return_value.edit.call_args.kwargs['embed'].description=='Removed by APBot'


def test_dry_run(harness):
    d,m,s,r,j=harness; d.bot.config['scam_detector_dry_run']=True
    asyncio.run(d.process(j)); m.delete.assert_not_called(); r.send.assert_not_called()


def test_default_dry_run(harness):
    d,m,s,r,j=harness; d.bot.config.pop('scam_detector_dry_run')
    asyncio.run(d.process(j)); m.delete.assert_not_called()


def test_staff_exempt(harness):
    d,m,s,r,j=harness; m.author=Member(True)
    asyncio.run(d.process(j)); m.delete.assert_not_called(); r.send.assert_not_called()


def test_legacy_staff_id_no_longer_grants_immunity(harness):
    d,m,s,r,j=harness; m.author.roles=[Role(1259554509559169159)]; asyncio.run(d.process(j)); m.delete.assert_awaited_once()


def test_staff_name(harness):
    d,m,s,r,j=harness; m.author.roles=[Role(5,'Trial Chat Moderator')]; asyncio.run(d.process(j)); m.delete.assert_not_called()


def test_unrelated_guild(harness):
    d,m,s,r,j=harness; d.bot.config['guild_id']=8; asyncio.run(d.process(j)); m.delete.assert_not_called()


def test_review_channel_privacy(harness):
    d,m,s,r,j=harness; r.permissions_for=lambda who:NS(view_channel=True,send_messages=True,embed_links=True,attach_files=True)
    asyncio.run(d.process(j)); m.delete.assert_not_called(); r.send.assert_not_called()


def test_role_leak(harness):
    d,m,s,r,j=harness; r.permissions_for=lambda who:NS(view_channel=who is not m.guild.default_role,send_messages=True,embed_links=True,attach_files=True)
    asyncio.run(d.process(j)); m.delete.assert_not_called()


def test_member_overwrite_leak(harness):
    d,m,s,r,j=harness; r.overwrites={m.author:NS(view_channel=True)}; asyncio.run(d.process(j)); m.delete.assert_not_called()


def test_changed_message(harness):
    d,m,s,r,j=harness; changed=NS(**vars(m)); changed.attachments=[]; s.fetch_message.side_effect=[m,changed]
    asyncio.run(d.process(j)); m.delete.assert_not_called(); assert r.send.await_count == 2


def test_report_not_deleted(harness):
    d,m,s,r,j=harness; m.content='Is this a scam?'; asyncio.run(d.process(j)); m.delete.assert_not_called()


def test_log_send_failure(harness):
    d,m,s,r,j=harness; r.send.side_effect=RuntimeError('no log')
    with pytest.raises(RuntimeError): asyncio.run(d.process(j))
    m.delete.assert_not_called()


def test_hash_bypasses_ocr(harness,monkeypatch):
    d,m,s,r,j=harness; data=b'example'; monkeypatch.setattr(rules,'KNOWN_IMAGES',{hashlib.sha256(data).hexdigest()}); m.content=''; m.attachments=[NS(id=5,filename='a.png',size=len(data),content_type='image/png',read=AsyncMock(return_value=data))]; d.ocr.scan=AsyncMock()
    result,digest=asyncio.run(d.assess(m)); assert result.delete and digest; d.ocr.scan.assert_not_called()


def test_repeated_clean_images_cached(harness):
    d,m,s,r,j=harness; data=b'clean'; m.content=''; m.attachments=[NS(id=5,filename='a.png',size=len(data),content_type='image/png',read=AsyncMock(return_value=data))]; d.ocr.scan=AsyncMock(return_value='AP Bio')
    async def run():
        assert await d.assess(m)==(None,None); assert await d.assess(m)==(None,None)
    asyncio.run(run()); d.ocr.scan.assert_awaited_once()


def test_ocr_failure_not_cached(harness):
    d,m,s,r,j=harness; data=b'clean'; m.content=''; m.attachments=[NS(id=5,filename='a.png',size=len(data),content_type='image/png',read=AsyncMock(return_value=data))]; d.ocr.scan=AsyncMock(side_effect=[None,BEAST])
    async def run():
        assert await d.assess(m)==(None,None); assert (await d.assess(m))[0].delete
    asyncio.run(run()); assert d.ocr.scan.await_count==2


def test_split_image_signals_do_not_combine(harness):
    d,m,s,r,j=harness; m.content=''; m.attachments=[NS(id=i,filename='a.png',size=1,content_type='image/png',read=AsyncMock(return_value=bytes([i]))) for i in (1,2)]; d.ocr.scan=AsyncMock(side_effect=['MrBeast crypto casino','Giving away $500 register promo code example.org withdraw instantly'])
    assert asyncio.run(d.assess(m))==(None,None)


def test_queue_bounds_and_dedup(harness):
    d,m,s,r,j=harness
    async def run():
        for i in range(20): d.enqueue(1,2,i)
        d.enqueue(1,2,0,edited=True)
        assert d.queue.qsize()==cog.QUEUE_SIZE; assert len(d.pending)==cog.QUEUE_SIZE; assert d.skipped==20-cog.QUEUE_SIZE; assert (2,0) in d.dirty
        d.cog_unload()
        await asyncio.gather(d.task,return_exceptions=True)
    asyncio.run(run())


def test_timeout_kills_worker(monkeypatch):
    monkeypatch.setattr(cog,'OCR_TIMEOUT',0.01); p=cog.OCRProcess(); p._exchange=AsyncMock(side_effect=lambda data: None)
    async def hang(data): await asyncio.sleep(10)
    p._exchange=hang; p.stop=AsyncMock(); assert asyncio.run(p.scan(b'a')) is None; p.stop.assert_awaited_once()


def test_cancellation_stops_ocr():
    p=cog.OCRProcess(); p.stop=AsyncMock()
    async def hang(data): await asyncio.sleep(10)
    p._exchange=hang
    async def run():
        t=asyncio.create_task(p.scan(b'a')); await asyncio.sleep(.01); t.cancel()
        with pytest.raises(asyncio.CancelledError): await t
    asyncio.run(run()); p.stop.assert_awaited_once()


def test_worker_rejects_corrupt_data_and_stops():
    async def run():
        p=cog.OCRProcess()
        try:
            assert await p.scan(b'not an image') is None
            assert p.proc is None
        finally:
            await p.stop()
    asyncio.run(run())


def test_worker_preprocessing_one_ocr_call(monkeypatch):
    from io import BytesIO
    Image=pytest.importorskip('PIL.Image')
    from utils import scam_ocr_worker as worker
    calls=[]
    def engine(data, **kwargs):
        with Image.open(BytesIO(data)) as im:
            assert max(im.size)<=worker.MAX_EDGE
        calls.append(kwargs)
        return [[None,'AP Biology',.99],[None,'noise',.1]],None
    monkeypatch.setattr(worker,'ENGINE',engine)
    b=BytesIO(); Image.new('RGB',(1700,800),'white').save(b,format='PNG')
    assert worker.extract(b.getvalue())=='AP Biology'; assert calls==[{'use_cls':False}]


def test_worker_skips_animated_images(monkeypatch):
    from io import BytesIO
    Image=pytest.importorskip('PIL.Image')
    from utils import scam_ocr_worker as worker
    b=BytesIO(); Image.new('RGB',(20,20),'white').save(b,format='GIF',save_all=True,append_images=[Image.new('RGB',(20,20),'black')],duration=100,loop=0)
    monkeypatch.setattr(worker,'ENGINE',lambda *a,**k: pytest.fail('animated image should not invoke OCR'))
    assert worker.extract(b.getvalue())==''

@pytest.mark.parametrize('caption', [BEAST, TRUMP, PAYOUT, BONUS, 'NSFW', 'free nitro'])
def test_text_only_never_queued_or_deleted(harness, caption):
    d,m,s,r,j=harness; m.content=caption; m.attachments=[]
    async def check():
        await d.on_message(m); await d.process(j)
    asyncio.run(check()); assert d.task is None; m.delete.assert_not_called(); d.ocr.scan.assert_not_called(); r.send.assert_not_called()


def test_scam_caption_with_unrelated_image_is_not_evidence(harness):
    d,m,s,r,j=harness; m.content=BEAST; d.ocr.scan=AsyncMock(return_value='AP Biology')
    asyncio.run(d.process(j)); m.delete.assert_not_called(); d.ocr.scan.assert_awaited_once()


@pytest.mark.parametrize('mime,filename', [('video/mp4','clip.mp4'),('image/gif','anim.gif'),('text/plain','a.png')])
def test_non_target_media_never_queued(harness,mime,filename):
    d,m,s,r,j=harness; m.attachments[0].content_type=mime; m.attachments[0].filename=filename
    asyncio.run(d.on_message(m)); assert d.task is None; d.ocr.scan.assert_not_called()


def test_non_image_raw_edit_not_queued(harness):
    d,m,s,r,j=harness
    payload=NS(guild_id=1,channel_id=2,message_id=7,data={'content':BEAST,'attachments':[{'filename':'a.mp4','size':300,'content_type':'video/mp4'}]})
    asyncio.run(d.on_raw_message_edit(payload)); assert d.task is None


def test_near_match_from_worker_is_enforced(harness):
    d,m,s,r,j=harness; d.ocr.scan=AsyncMock(return_value=rules.Match('near-identical known campaign screenshot'))
    asyncio.run(d.process(j)); m.delete.assert_awaited_once()


def test_other_celebrities_not_matched():
    for name in ('Elon Musk','Taylor Swift','Trumpet','trump'):
        assert rules.classify_image_text(BEAST.replace('MrBeast',name)) is None


def test_visual_fingerprint_negative_controls():
    from PIL import Image, ImageDraw
    from utils.scam_visual import near_copy
    for color in ('white','black','navy','gray'):
        im=Image.new('RGB',(814,1123),color); assert not near_copy(im)
        ImageDraw.Draw(im).rectangle((50,50,250,400),fill='green'); assert not near_copy(im)


def test_worker_visual_match_short_circuits_ocr(monkeypatch):
    from io import BytesIO
    from PIL import Image
    from utils import scam_ocr_worker as worker
    monkeypatch.setattr(worker,'near_copy',lambda im: True)
    monkeypatch.setattr(worker,'ENGINE',lambda *a,**kw: pytest.fail('should not invoke OCR'))
    b=BytesIO(); Image.new('RGB',(300,400),'navy').save(b,format='PNG')
    assert worker.extract(b.getvalue()) is worker.NEAR_MATCH


def test_third_person_casino_news_not_deleted():
    assert rules.classify_image_text('Donald Trump crypto casino giveaway $5600 register at news.example.com promo code withdraw instantly') is None


def test_known_domain_ocr_spacing():
    assert rules.classify_image_text(BEAST.replace('pusawin.com','pusawin . com')).delete
