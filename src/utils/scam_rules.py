"""High-confidence indicators for the celebrity crypto-casino campaign only."""
from dataclasses import dataclass
import hashlib
import re
import unicodedata

# Exact SHA-256 fingerprints of confirmed campaign screenshots supplied by staff.
# No screenshots, account information or wallet addresses are stored in the repository.
KNOWN_IMAGES = frozenset({
    '82e4c3ae43ac364d5d9ca8671ddd7bcddca279546c3bff87d8730f59d498a099',
    'c246c7bd45d8a13f6da17070c9c4a3da6be968d451e005f750f32c698d2c9854',
    '2d21c6f8620877a5e24005292bf10e87dbb954081701c0972ab95d919ec5f31f',
    'b5ee75ceb48502ed6ceafba8627af8c36855759e84fae1b3f207df6e6b93ecc3',
    '4c32a67a066c53f27ce35ac8caa2318b2c6fabb705afc950e8cf5d069615a02c',
    '2129df3768d9945ba0c4b6c63ca6f78ea6cd203bc72ccb2864e9d27bf9d6a577',
    '2dc6836824137847c4fb80c32982845d37c77e8d1371903eadb21066d01ad773',
    'dc37db6bbcc09a5ab7fb93b675a5f5943434699addf873001b7f37c173f00d35',
    'b1353510d01d51dec2d7ccf4653ed11f1f4189b0334e1cc3ad9aa7f30c05ee1c',
    '1c1e19be7780431b593f2a38dea32ff67610f49e9d4eccb68aa4e652d569e91b',
    '23c2a814b572557e8d731dae5f917474503df4425d296c1675ef23a8d2631238',
})

DOMAIN = re.compile(r'(?<![\w.-])(?:vanowin|pusawin|meorox|luckato|cinchwin)\s*\.\s*com(?![\w-]|\.[a-z0-9-])')
EXTERNAL = re.compile(r'(?<![\w.-])([a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|gg|app|vip|win|xyz|site|me|bet|casino))(?![\w-]|\.[a-z0-9-])')
CELEBRITY = re.compile(r'\b(?:mr\s*beast|donald\s+(?:j\.?\s*)?trump|realdonaldtrump)\b')
CASINO = re.compile(r'\b(?:crypto(?:currency)?\s+casino|casino\b.{0,100}\bcrypto(?:currency)?|crypto(?:currency)?\b.{0,100}\bcasino)\b')
REWARD = re.compile(r'\b(?:giving away|give away|giveaway|bonus|reward|free)\b')
AMOUNT = re.compile(r'\$\s*\d[\d,. ]{1,14}|\b\d[\d,. ]{1,14}\s*(?:usd[ct]?|dollars)\b')
CAMPAIGN = re.compile(r'\b(?:withdraw(?:al)?\b.{0,80}\b(?:instantly|immediately)|(?:post|tweet) will be deleted|only the fastest)\b')
FIRST_PERSON = re.compile(r'\bmy\s+(?:very\s+)?own\s+(?:crypto(?:currency)?\s+)?casino\b|\b(?:i am|i.m|we are|we.re)\s+(?:pleased|excited|happy)\s+to\s+announce\b')
PROMO_CODE = re.compile(r'\bpromo(?:tional)?\s+code\b')
CLAIM = re.compile(r'\b(?:claim (?:your|the) (?:reward|bonus|prize)|promo(?:tional)?\s+code|register(?:s|ed)?|sign\s*up|activate\s+code)\b')
WITHDRAW = re.compile(r'\bwithdrawal\s+(?:success|successful)|\bwithdrawal\b.{0,85}\b(?:successful|successfully)\b')
WALLET = re.compile(r'\b(?:wallet|usdt|usdc|crypto(?:currency)?)\b')
# Explicit reporting context is review-only, not a bypass to a different scan path.
REPORT = re.compile(r'\b(?:is (?:this|that) (?:a )?scam|(?:reporting|reported) (?:a |this |the )?scam|(?:this|that) is (?:a |the )?(?:scam|fake)|scam (?:warning|awareness|example|evidence)|do not (?:click|deposit|register)|don.t (?:click|deposit|register))\b')

@dataclass(frozen=True)
class Match:
    reason: str
    delete: bool = True


def normalize(value):
    value = unicodedata.normalize('NFKC', str(value or '')[:24000]).casefold()
    value = ''.join(c for c in value if unicodedata.category(c) != 'Cf')
    return re.sub(r'\s+', ' ', value).strip()


def report_context(text):
    return bool(REPORT.search(normalize(text)))


def image_match(data):
    return Match('known campaign screenshot') if hashlib.sha256(data).hexdigest() in KNOWN_IMAGES else None


def classify_image_text(text):
    """Classify OCR text from one image only; never call on Discord captions."""
    t = normalize(text)
    known = bool(DOMAIN.search(t))
    external = known or any(not (d in {'x.com', 'twitter.com', 'youtube.com', 'discord.com', 'mrbeast.com', 'donaldjtrump.com'} or d.endswith(('.x.com', '.twitter.com', '.youtube.com', '.discord.com'))) for d in EXTERNAL.findall(t))
    promo = bool(CELEBRITY.search(t) and CASINO.search(t) and FIRST_PERSON.search(t) and REWARD.search(t) and AMOUNT.search(t) and CLAIM.search(t) and external and (known or (PROMO_CODE.search(t) and CAMPAIGN.search(t))))
    payout = bool(known and WITHDRAW.search(t) and AMOUNT.search(t) and WALLET.search(t))
    bonus = bool(known and 'activate code for bonus' in t and 'promo code' in t)
    if promo or payout or bonus:
        return Match('celebrity crypto-casino promotion' if promo else 'known casino payout/bonus screenshot', not report_context(t))
    return None
