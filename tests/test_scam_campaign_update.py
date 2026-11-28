"""New confirmed campaign sample and bounded second-pass OCR tests."""
from io import BytesIO
from PIL import Image
import pytest
from utils import scam_rules as rules, scam_visual as visual, scam_ocr_worker as worker

NEW_AD = "MrBeast I am pleased to announce the launch of my own cryptocurrency casino. I am giving away $3,200 to everyone who registers, and you can withdraw the bonus immediately. How to claim your reward: Go to meorox.com. Enter the special promo code: CASH. Receive your $3,200 bonus. This post will be deleted one hour after publication."


def test_reference_added():
    assert 'b5ee75ceb48502ed6ceafba8627af8c36855759e84fae1b3f207df6e6b93ecc3' in rules.KNOWN_IMAGES
    assert (6532, 28674334460106565113088096568712674615955781561401107961020171366774053741, 3617647133879132872111242986517675200916304031669911032415384573828571119615, 903190146771620268097378950018664913864376049381391270604600026395842711552) in visual.REFERENCES

@pytest.mark.parametrize('domain', ['meorox.com','anotherexample.net','meorox . com'])
def test_new_campaign_transcript(domain):
    assert rules.classify_image_text(NEW_AD.replace('meorox.com', domain)).delete

@pytest.mark.parametrize('text', ['MrBeast new Beast Games season', 'Donald Trump news', 'meorox.com', 'Elon Musk ' + NEW_AD.replace('MrBeast',''), 'MrBeast cryptocurrency casino', 'MrBeast announces $3200 giveaway'])
def test_no_weaker_classification(text):
    assert rules.classify_image_text(text) is None


def sample():
    b = BytesIO(); Image.new('RGB',(648,992),'navy').save(b,format='PNG'); return b.getvalue()

@pytest.mark.parametrize('first,second,expected,calls', [
    ('MrBeast', NEW_AD.replace('MrBeast',''), True, 2),
    ('MrBeast crypto casino', 'ordinary content', False, 2),
    ('AP Biology', NEW_AD, False, 1),
    (NEW_AD, 'unused', True, 1),
    ('MrBeast scam warning', NEW_AD, False, 1),
    ('MrBeast', 'new Beast Games season', False, 2),
])
def test_second_pass(monkeypatch,first,second,expected,calls):
    seen=[]
    def engine(data,**kwargs):
        with Image.open(BytesIO(data)) as im:
            assert max(im.size) <= worker.MAX_EDGE
        seen.append(data)
        return [[None, first if len(seen)==1 else second, .99]], None
    monkeypatch.setattr(worker,'ENGINE',engine)
    monkeypatch.setattr(worker,'near_copy',lambda im:False)
    result=rules.classify_image_text(worker.extract(sample()))
    assert bool(result and result.delete) is expected
    assert len(seen)==calls


def test_retry_does_not_extend_to_unrelated_images():
    assert not worker.retry_needed('AP Calculus homework',648,992)
    assert not worker.retry_needed('',648,992)
    assert worker.retry_needed('cryptocurrency casino promo code claim your reward',648,992)
