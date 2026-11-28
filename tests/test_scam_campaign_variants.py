"""Additional confirmed campaign references and conservative OCR regressions."""
import pytest
from utils import scam_rules as rules, scam_visual as visual, scam_ocr_worker as worker

REFERENCES = {'b5ee75ceb48502ed6ceafba8627af8c36855759e84fae1b3f207df6e6b93ecc3': (6532, 28674334460106565113088096568712674615955781561401107961020171366774053741, 3617647133879132872111242986517675200916304031669911032415384573828571119615, 903190146771620268097378950018664913864376049381391270604600026395842711552), '82e4c3ae43ac364d5d9ca8671ddd7bcddca279546c3bff87d8730f59d498a099': (11590, 15781724957323878653174366492807135525293130953047142701564725085432638312035, 276069037392825503939766365095151884621169233115308984315319421035954177, 1765579104798348340493050163105092317951756236952927089326879595287190782), 'c246c7bd45d8a13f6da17070c9c4a3da6be968d451e005f750f32c698d2c9854': (7500, 46828787660747285689957709119765197182469949471964420518940384685570941137178, 1759965537981780105100488824650411184094029475702299649544226542939216255, 1766825159776728840230862487116783075969769400639055101514379128240275568), '2d21c6f8620877a5e24005292bf10e87dbb954081701c0972ab95d919ec5f31f': (7502, 70603495944189315621832399088273446205089812252029370060321866975944582267174, 232729485827741754467982943695099564476748194964243470603851641196938243868, 663440699914046433609002056482644869918235179238760693295453756645441536)}

@pytest.mark.parametrize("digest,fp", REFERENCES.items())
def test_reference_present(digest, fp):
    assert digest in rules.KNOWN_IMAGES
    assert fp in visual.REFERENCES

@pytest.mark.parametrize("domain", ["luckato.com", "cinchwin.com", "meorox.com"])
def test_known_domain_support(domain):
    assert rules.classify_image_text(f"{domain}/profile/bonuses Activate Code for Bonus Enter the promo code Rakeback").delete
    assert rules.classify_image_text(f"{domain}/profile/withdraw Withdrawal Success $2700 USDT wallet").delete

@pytest.mark.parametrize("text", [
    "Activate Code for Bonus Enter the promo code Rakeback VIP-Club",
    "Withdrawal Success $2700 USDT wallet money transferred to your specified wallet",
    "example.com/profile/bonuses Activate Code for Bonus Enter the promo code Rakeback",
    "luckato.com", "cinchwin.com", "MrBeast and Donald Trump news",
    "evil.cinchwin.com.evil.net Activate Code for Bonus Enter the promo code Rakeback",
])
def test_no_generic_casino_or_domain_only_punishment(text):
    assert rules.classify_image_text(text) is None

@pytest.mark.parametrize("text", [
    "Activate Code for Bonus Rakeback VIP-Club",
    "Select a Withdraw Method Enter Wallet Address Withdrawal Success USDT",
    "cinchwin.com bonuses",
])
def test_support_retry(text):
    assert worker.retry_needed(text, 960, 1280)

@pytest.mark.parametrize("text", ["", "AP Biology homework", "USDT wallet", "Rakeback", "scam warning Activate Code for Bonus Rakeback VIP-Club"])
def test_no_unnecessary_retry(text):
    assert not worker.retry_needed(text, 960, 1280)


def test_known_report_is_review_only():
    m = rules.classify_image_text("scam warning cinchwin.com Activate Code for Bonus Enter the promo code")
    assert m and not m.delete
