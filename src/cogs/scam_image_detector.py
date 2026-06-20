from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Optional

import nextcord
from nextcord.ext import commands

from bot_base import APBot


log = logging.getLogger(__name__)


DEFAULT_ENABLED_BOT_IDS = {1508281890820460604, 1464966749643341847}
REVIEW_CHANNEL_ID = 1517350483646484480
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v", ".mkv"}
MAX_SCAN_BYTES = 8 * 1024 * 1024
MAX_VIDEO_SCAN_BYTES = 32 * 1024 * 1024
MAX_OCR_FRAMES = 3
MAX_VIDEO_FRAMES = 5
OCR_CONFIDENCE_THRESHOLD = 0.45
NSFW_SCORE_THRESHOLD = 0.55

LOW_RISK = "low"
MEDIUM_RISK = "medium"
HIGH_RISK = "high"
ALERT_THRESHOLD = 70
REVIEW_THRESHOLD = 45

URL_RE = re.compile(r"https?://|discord\.gift|discord\.gg|www\.", re.IGNORECASE)
URL_TOKEN_RE = re.compile(r"https?://\S+", re.IGNORECASE)
SHORTENER_RE = re.compile(
    r"\b(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|is\.gd|cutt\.ly|rebrand\.ly|rb\.gy)\b",
    re.IGNORECASE,
)
SUSPICIOUS_DOMAIN_RE = re.compile(
    r"\b[\w.-]+\.(?:ru|cn|top|xyz|click|link|zip|mov|work|live|site|online|shop|gift|claim|win)\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"(?:\$\s?\d"
    r"|\d[\d,]*\s*(?:k\b|grand|dollars?|usd|euros?|pounds?|bucks|thousand|million|billion)"
    r"|(?:hundred|thousand|million|billion)\s+(?:dollars?|usd|euros?|pounds?|bucks)"
    r"|\bdollars?\b|\beuros?\b"
    r"|usd|cash(?:\s*app)?|money|gift\s*card|nitro|robux|v-?bucks|crypto|bitcoin|btc|eth|paypal|venmo|zelle)",
    re.IGNORECASE,
)
HANDLE_RE = re.compile(r"@(?:everyone|here|[\w.-]{2,32})", re.IGNORECASE)
DM_LURE_RE = re.compile(
    r"\b(?:dm|dms|pm|pms|msg|message|inbox|hmu|contact|text|add)\s+me\b"
    r"|\bdm\s+(?:me|us)\b"
    r"|\bfirst\s+(?:\d+|person|people|few|one|to)\b"
    r"|\bwho(?:ever)?\s+(?:dms|messages|pms|contacts)\b",
    re.IGNORECASE,
)
HOOK_RE = re.compile(
    r"\b(?:get|getting|become|becoming)\s+rich\b"
    r"|\brich\s+quick\b"
    r"|\bmake\s+money\s+fast\b"
    r"|\bquick\s+(?:money|cash)\b"
    r"|\bchance\s+to\s+win\b"
    r"|\bwin\s+(?:\$|\d|big|one\s+(?:hundred|thousand|million|billion))",
    re.IGNORECASE,
)
OFF_PLATFORM_RE = re.compile(
    r"\b(?:telegram|whatsapp|whats\s*app|signal|wechat|kik|snapchat|t\.me)\b",
    re.IGNORECASE,
)
BARE_DOMAIN_RE = re.compile(
    r"\b[\w-]{2,}\.(?:com|net|org|io|me|gg|co|app|info|biz|live|online|site|shop|store|vip|win|top|fun|cc|tk|ml|xyz|click|link)\b",
    re.IGNORECASE,
)

BRAND_TERMS = (
    "mrbeast",
    "mr beast",
    "discord",
    "nitro",
    "steam",
    "roblox",
    "fortnite",
    "cash app",
    "paypal",
    "apple",
    "amazon",
    "google",
    "youtube",
)
GIVEAWAY_TERMS = (
    "giveaway",
    "winner",
    "won",
    "prize",
    "reward",
    "free",
    "limited time",
    "congratulations",
    "selected",
    "airdrop",
    "giving away",
    "give away",
    "handing out",
    "free money",
    "free cash",
)
STRONG_ACTION_TERMS = (
    "claim",
    "verify",
    "register",
    "login",
    "log in",
    "sign in",
    "sign up",
    "redeem",
    "promo code",
    "scan qr",
    "scan the qr",
    "connect wallet",
    "seed phrase",
    "password",
    "enter code",
    "payment",
    "withdrawal",
)
WEAK_ACTION_TERMS = (
    "click",
    "tap",
    "visit",
    "page",
    "continue",
    "follow",
    "subscribe",
)
PARODY_TERMS = (
    "joke",
    "meme",
    "parody",
    "satire",
    "fake",
    "shitpost",
    "sketch",
    "drawing",
    "drawn",
)
NSFW_CLASSES = {
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "EXPOSED_ANUS",
    "EXPOSED_BUTTOCKS",
    "EXPOSED_BREAST",
    "EXPOSED_BREASTS",
    "EXPOSED_VAGINA",
    "EXPOSED_PENIS",
}

_rapid_ocr = None
_rapid_ocr_unavailable = False
_nude_detector = None
_nude_detector_unavailable = False


@dataclass(frozen=True)
class ScamAssessment:
    score: int
    level: str
    reasons: tuple[str, ...]
    scanned_text: str = ""
    content_kind: str = "image"

    @property
    def should_alert(self) -> bool:
        return self.score >= ALERT_THRESHOLD


def normalize_text(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def contains_any(text: str, terms: Iterable[str]) -> bool:
    return any(term in text for term in terms)


def score_to_level(score: int) -> str:
    if score >= ALERT_THRESHOLD:
        return HIGH_RISK
    if score >= REVIEW_THRESHOLD:
        return MEDIUM_RISK
    return LOW_RISK


def assess_scam_text(
    text: str,
    *,
    has_qr: bool = False,
    has_visual_attachment: bool = True,
    nsfw_detections: Iterable[str] = (),
    content_kind: str = "image",
) -> ScamAssessment:
    normalized = normalize_text(text)
    score = 0
    reasons: list[str] = []
    nsfw_detections = tuple(nsfw_detections)

    if has_visual_attachment:
        score += 5

    if nsfw_detections:
        score += 100
        reasons.append("detects explicit or adult visual content")

    has_brand = contains_any(normalized, BRAND_TERMS)
    has_money = bool(MONEY_RE.search(normalized))
    has_hook = bool(HOOK_RE.search(normalized))
    has_giveaway = contains_any(normalized, GIVEAWAY_TERMS) or has_money or has_hook
    has_strong_action = contains_any(normalized, STRONG_ACTION_TERMS)
    has_weak_action = contains_any(normalized, WEAK_ACTION_TERMS)
    has_dm_lure = bool(DM_LURE_RE.search(normalized))
    has_off_platform = bool(OFF_PLATFORM_RE.search(normalized))
    has_bare_domain = bool(BARE_DOMAIN_RE.search(normalized))
    has_url = bool(URL_RE.search(normalized) or SHORTENER_RE.search(normalized) or SUSPICIOUS_DOMAIN_RE.search(normalized))
    has_parody = contains_any(normalized, PARODY_TERMS)

    if has_brand:
        score += 15
        reasons.append("mentions an impersonation-prone brand or creator")

    if has_giveaway:
        score += 20
        reasons.append("uses giveaway, prize, money, or reward language")

    if has_strong_action:
        score += 25
        reasons.append("asks users to claim, verify, log in, scan, or enter sensitive info")
    elif has_weak_action:
        score += 5
        reasons.append("uses weak call-to-action language")

    if has_dm_lure:
        score += 25
        reasons.append("asks people to DM, contact privately, or be the 'first' to respond")

    if has_money and has_dm_lure:
        score += 30
        reasons.append("offers money or prizes in exchange for DMing or contacting privately")
    elif has_giveaway and has_dm_lure:
        score += 10
        reasons.append("combines giveaway or free-stuff language with a request to contact privately")

    if has_bare_domain and not has_url:
        score += 20
        reasons.append("points users to an external website")

    if has_off_platform and (has_dm_lure or has_url or has_bare_domain):
        score += 20
        reasons.append("tries to move users to an off-platform app like Telegram or WhatsApp")

    if has_url:
        score += 30
        reasons.append("contains a link or suspicious domain")

    if has_qr:
        score += 30
        reasons.append("contains a QR code")

    if HANDLE_RE.search(normalized) and has_giveaway:
        score += 10
        reasons.append("combines a mention with reward language")

    if has_brand and has_giveaway and (has_strong_action or has_url or has_qr):
        score += 15
        reasons.append("combines brand impersonation, reward language, and a risky action")

    if has_brand and has_giveaway and has_weak_action and not has_strong_action and not has_url and not has_qr:
        score += 25
        reasons.append("looks like a creator giveaway ad asking users to visit or continue")

    if has_parody and not has_url and not has_qr and not has_strong_action:
        score = max(0, score - 25)
        reasons.append("looks like a joke/parody without a link, QR code, or account action")

    score = min(score, 100)
    if score < REVIEW_THRESHOLD and not reasons:
        reasons.append("no strong scam signals found")

    return ScamAssessment(
        score=score,
        level=score_to_level(score),
        reasons=tuple(reasons),
        scanned_text=clip(text, 500),
        content_kind=content_kind,
    )


def is_visual_attachment(attachment) -> bool:
    content_type = normalize_text(getattr(attachment, "content_type", ""))
    filename = normalize_text(getattr(attachment, "filename", ""))
    suffix = Path(filename).suffix
    return content_type.startswith("image/") or suffix in IMAGE_EXTENSIONS


def is_video_attachment(attachment) -> bool:
    content_type = normalize_text(getattr(attachment, "content_type", ""))
    filename = normalize_text(getattr(attachment, "filename", ""))
    suffix = Path(filename).suffix
    return content_type.startswith("video/") or suffix in VIDEO_EXTENSIONS


def clean_url(value: str) -> str:
    return str(value or "").strip("<>()[]{}.,!?")


def is_visual_url(value: str) -> bool:
    url = clean_url(value).lower()
    without_query = url.split("?", 1)[0].split("#", 1)[0]
    return (
        without_query.endswith(tuple(IMAGE_EXTENSIONS))
        or "tenor.com/view/" in url
        or "giphy.com/gifs/" in url
        or "media.discordapp.net/" in url
        or "cdn.discordapp.com/" in url
    )


def visual_urls_from_message(message) -> list[str]:
    urls = [clean_url(match.group(0)) for match in URL_TOKEN_RE.finditer(getattr(message, "content", "") or "")]

    for embed in getattr(message, "embeds", []) or []:
        for attr_name in ("image", "thumbnail"):
            embed_image = getattr(embed, attr_name, None)
            image_url = getattr(embed_image, "url", None)
            if image_url:
                urls.append(clean_url(image_url))

    return [url for url in urls if is_visual_url(url)]


def attachment_label(attachment) -> str:
    filename = getattr(attachment, "filename", None) or "attachment"
    url = getattr(attachment, "url", None) or getattr(attachment, "proxy_url", None)
    if url:
        return f"[{filename}]({url})"
    return f"`{filename}`"


def attachment_lines(message) -> list[str]:
    return [attachment_label(attachment) for attachment in getattr(message, "attachments", [])]


def clip(text: str, limit: int = 1000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n... *(truncated)*"


def optional_ocr_available() -> bool:
    if get_rapid_ocr() is not None:
        return True

    try:
        import PIL.Image
        import pytesseract
    except ImportError:
        return False
    return True


def optional_qr_available() -> bool:
    try:
        import pyzbar.pyzbar
        import PIL.Image
    except ImportError:
        return False
    return True


def optional_nudity_available() -> bool:
    return get_nude_detector() is not None


def get_rapid_ocr():
    global _rapid_ocr, _rapid_ocr_unavailable
    if _rapid_ocr_unavailable:
        return None
    if _rapid_ocr is not None:
        return _rapid_ocr

    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        _rapid_ocr_unavailable = True
        return None

    try:
        _rapid_ocr = RapidOCR()
    except Exception:
        _rapid_ocr_unavailable = True
        return None

    return _rapid_ocr


def get_nude_detector():
    global _nude_detector, _nude_detector_unavailable
    if _nude_detector_unavailable:
        return None
    if _nude_detector is not None:
        return _nude_detector

    try:
        from nudenet import NudeDetector
    except ImportError:
        _nude_detector_unavailable = True
        return None

    try:
        _nude_detector = NudeDetector()
    except Exception:
        _nude_detector_unavailable = True
        return None

    return _nude_detector


def extract_text_with_rapidocr(data: bytes) -> str:
    engine = get_rapid_ocr()
    if engine is None:
        return ""

    try:
        result, _ = engine(data)
    except Exception:
        return ""

    if not result:
        return ""

    lines = []
    for item in result:
        if len(item) < 3:
            continue
        text = str(item[1] or "").strip()
        try:
            confidence = float(item[2])
        except (TypeError, ValueError):
            confidence = 0
        if text and confidence >= OCR_CONFIDENCE_THRESHOLD:
            lines.append(text)

    return "\n".join(lines)


def detect_nsfw_with_nudenet(data: bytes) -> tuple[str, ...]:
    detector = get_nude_detector()
    if detector is None:
        return ()

    try:
        detections = detector.detect(data)
    except Exception:
        return ()

    unsafe = []
    for detection in detections or []:
        label = normalize_text(detection.get("class", "")).upper().replace(" ", "_")
        try:
            score = float(detection.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        if label in NSFW_CLASSES and score >= NSFW_SCORE_THRESHOLD:
            unsafe.append(f"{label} ({score:.2f})")

    return tuple(unsafe)


def scan_video_bytes(data: bytes, suffix: str = ".mp4") -> tuple[str, bool, tuple[str, ...]]:
    try:
        import cv2
    except ImportError:
        return "", False, ()

    temp_path = None
    text_parts: list[str] = []
    has_qr = False
    nsfw_detections: list[str] = []

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix or ".mp4", delete=False) as temp_file:
            temp_file.write(data)
            temp_path = temp_file.name

        capture = cv2.VideoCapture(temp_path)
        if not capture.isOpened():
            return "", False, ()

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count > 0:
            frame_indexes = [
                int((index + 1) * frame_count / (MAX_VIDEO_FRAMES + 1))
                for index in range(MAX_VIDEO_FRAMES)
            ]
        else:
            frame_indexes = list(range(MAX_VIDEO_FRAMES))

        for frame_index in frame_indexes:
            if frame_index > 0:
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

            ok, frame = capture.read()
            if not ok:
                continue

            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                continue

            frame_bytes = encoded.tobytes()
            extracted_text, frame_has_qr = extract_text_from_image_bytes(frame_bytes)
            if extracted_text:
                text_parts.append(extracted_text)
            has_qr = has_qr or frame_has_qr
            nsfw_detections.extend(detect_nsfw_with_nudenet(frame_bytes))

        capture.release()
    except Exception:
        return "", False, ()
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    return "\n".join(text_parts), has_qr, tuple(nsfw_detections)


def extract_text_from_image_bytes(data: bytes) -> tuple[str, bool]:
    text_parts: list[str] = []
    has_qr = False
    rapid_text = extract_text_with_rapidocr(data)
    if rapid_text:
        text_parts.append(rapid_text)

    try:
        from PIL import Image, ImageSequence
    except ImportError:
        return "", False

    try:
        image = Image.open(BytesIO(data))
    except Exception:
        return "", False

    frames = []
    try:
        for index, frame in enumerate(ImageSequence.Iterator(image)):
            if index >= MAX_OCR_FRAMES:
                break
            frames.append(frame.convert("RGB"))
    except Exception:
        frames = [image.convert("RGB")]

    try:
        import pytesseract
    except ImportError:
        pytesseract = None

    try:
        from pyzbar.pyzbar import decode as decode_qr
    except ImportError:
        decode_qr = None

    for frame in frames:
        if pytesseract is not None:
            try:
                text = pytesseract.image_to_string(frame)
                if text:
                    text_parts.append(text)
            except Exception:
                pass

        if decode_qr is not None:
            try:
                decoded = decode_qr(frame)
                if decoded:
                    has_qr = True
                    for code in decoded:
                        data_text = getattr(code, "data", b"")
                        if isinstance(data_text, bytes):
                            data_text = data_text.decode("utf-8", errors="ignore")
                        if data_text:
                            text_parts.append(str(data_text))
            except Exception:
                pass

    return "\n".join(text_parts), has_qr


class ScamImageDetector(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    def _config_get(self, key, default=None):
        config = getattr(self.bot, "config", None)
        if config is None:
            return default
        return config.get(key, default)

    def enabled_bot_ids(self) -> set[int]:
        configured_ids = set(DEFAULT_ENABLED_BOT_IDS)
        config = getattr(self.bot, "config", None)

        if config is not None:
            application_id = config.get("application_id")
            if application_id is not None:
                try:
                    configured_ids.add(int(application_id))
                except (TypeError, ValueError):
                    pass

            for bot_id in config.get("scam_detector_enabled_bot_ids", []) or []:
                try:
                    configured_ids.add(int(bot_id))
                except (TypeError, ValueError):
                    pass

        return configured_ids

    def is_enabled_for_current_bot(self) -> bool:
        if getattr(self.bot, "scam_detector_always_enabled", False):
            return True
        bot_user_id = getattr(getattr(self.bot, "user", None), "id", None)
        return bot_user_id is None or bot_user_id in self.enabled_bot_ids()

    async def scan_attachment(self, attachment) -> tuple[str, bool, tuple[str, ...]]:
        if not is_visual_attachment(attachment):
            return "", False, ()

        if not optional_ocr_available() and not optional_qr_available() and not optional_nudity_available():
            return "", False, ()

        size = getattr(attachment, "size", 0) or 0
        if size > MAX_SCAN_BYTES:
            return "", False, ()

        try:
            data = await attachment.read()
        except (nextcord.HTTPException, AttributeError):
            return "", False, ()

        extracted_text, has_qr = await asyncio.to_thread(extract_text_from_image_bytes, data)
        nsfw_detections = await asyncio.to_thread(detect_nsfw_with_nudenet, data)
        return extracted_text, has_qr, nsfw_detections

    async def scan_video_attachment(self, attachment) -> tuple[str, bool, tuple[str, ...]]:
        if not is_video_attachment(attachment):
            return "", False, ()

        size = getattr(attachment, "size", 0) or 0
        if size > MAX_VIDEO_SCAN_BYTES:
            return "", False, ()

        try:
            data = await attachment.read()
        except (nextcord.HTTPException, AttributeError):
            return "", False, ()

        suffix = Path(normalize_text(getattr(attachment, "filename", ""))).suffix or ".mp4"
        return await asyncio.to_thread(scan_video_bytes, data, suffix)

    async def assess_message(self, message: nextcord.Message) -> Optional[ScamAssessment]:
        visual_attachments = [
            attachment for attachment in getattr(message, "attachments", []) if is_visual_attachment(attachment)
        ]
        video_attachments = [
            attachment for attachment in getattr(message, "attachments", []) if is_video_attachment(attachment)
        ]
        visual_urls = visual_urls_from_message(message)
        has_media = bool(visual_attachments or video_attachments or visual_urls)

        text_parts = [getattr(message, "content", "")]
        has_qr = False
        nsfw_detections = []
        content_kind = "video" if video_attachments and not visual_attachments and not visual_urls else "image"

        for attachment in visual_attachments:
            text_parts.append(getattr(attachment, "filename", ""))
            extracted_text, attachment_has_qr, attachment_nsfw_detections = await self.scan_attachment(attachment)
            if extracted_text:
                text_parts.append(extracted_text)
            has_qr = has_qr or attachment_has_qr
            nsfw_detections.extend(attachment_nsfw_detections)

        for attachment in video_attachments:
            text_parts.append(getattr(attachment, "filename", ""))
            extracted_text, attachment_has_qr, attachment_nsfw_detections = await self.scan_video_attachment(attachment)
            if extracted_text:
                text_parts.append(extracted_text)
            has_qr = has_qr or attachment_has_qr
            nsfw_detections.extend(attachment_nsfw_detections)

        assessment = assess_scam_text(
            "\n".join(text_parts),
            has_qr=has_qr,
            has_visual_attachment=has_media,
            nsfw_detections=nsfw_detections,
            content_kind=content_kind if has_media else "text",
        )

        if not has_media and not assessment.should_alert:
            return None
        return assessment

    async def get_forward_channel(self):
        channel = self.bot.get_channel(REVIEW_CHANNEL_ID)
        if channel is not None:
            return channel
        try:
            return await self.bot.fetch_channel(REVIEW_CHANNEL_ID)
        except (AttributeError, nextcord.Forbidden, nextcord.NotFound, nextcord.HTTPException) as exc:
            log.warning("Unable to access review channel %s: %s", REVIEW_CHANNEL_ID, exc)
            return None

    def build_alert_embed(self, message: nextcord.Message, assessment: ScamAssessment) -> nextcord.Embed:
        attachments = attachment_lines(message)
        original_content = getattr(message, "content", "") or ""
        author = getattr(message, "author", None)
        author_id = getattr(author, "id", "unknown")
        author_name = str(author) if author else str(author_id)
        channel = getattr(message, "channel", None)
        channel_name = getattr(channel, "name", None) or "unknown channel"
        channel_id = getattr(channel, "id", "?")

        embed = nextcord.Embed(
            title="Possible Unsafe Message Detected",
            description=(
                "This was forwarded for human review. The bot did not delete the original message or re-upload media."
            ),
            color=nextcord.Color.orange(),
        )
        embed.add_field(name="User", value=f"{author_name} (`{author_id}`)", inline=False)
        embed.add_field(name="Channel", value=f"#{channel_name} (`{channel_id}`)", inline=True)
        embed.add_field(name="Risk", value=f"{assessment.level.title()} ({assessment.score}/100)", inline=True)
        embed.add_field(name="Reasons", value=clip("\n".join(f"- {reason}" for reason in assessment.reasons), 1000), inline=False)
        if original_content:
            embed.add_field(name="Original Text", value=clip(original_content, 1000), inline=False)
        if assessment.scanned_text:
            embed.add_field(name="Scanned Text", value=clip(f"`{assessment.scanned_text}`", 1000), inline=False)

        jump_url = getattr(message, "jump_url", None)
        if jump_url:
            embed.add_field(name="Message", value=f"[Jump to message]({jump_url})", inline=False)

        if attachments:
            embed.add_field(name="Attachments", value=clip("\n".join(attachments), 1000), inline=False)

        return embed

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message) -> None:
        if not self.is_enabled_for_current_bot():
            return

        if getattr(message, "guild", None) is None:
            return

        if getattr(getattr(message, "author", None), "bot", False):
            return

        source_channel_id = getattr(getattr(message, "channel", None), "id", None)
        if source_channel_id == REVIEW_CHANNEL_ID:
            return

        assessment = await self.assess_message(message)
        if assessment is None:
            return

        if not assessment.should_alert:
            return

        alert_channel = await self.get_forward_channel()
        if alert_channel is None:
            return

        embed = self.build_alert_embed(message, assessment)
        try:
            await alert_channel.send(
                content=None,
                embed=embed,
                allowed_mentions=nextcord.AllowedMentions.none(),
            )
        except (nextcord.Forbidden, nextcord.HTTPException) as exc:
            log.warning("Unable to forward message %s: %s", getattr(message, "id", "unknown"), exc)


def setup(bot: APBot) -> None:
    bot.add_cog(ScamImageDetector(bot))
