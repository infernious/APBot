import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cogs.scam_image_detector import (
    ALERT_THRESHOLD,
    DEFAULT_ENABLED_BOT_IDS,
    REVIEW_CHANNEL_ID,
    REVIEW_THRESHOLD,
    ScamImageDetector,
    assess_scam_text,
    is_visual_attachment,
    is_visual_url,
    is_video_attachment,
)
from startup import DEFAULT_COGS


def attachment(filename="scam.png", content_type="image/png", url="https://cdn.discordapp.com/scam.png"):
    return SimpleNamespace(
        filename=filename,
        content_type=content_type,
        url=url,
        proxy_url=None,
        size=1024,
        read=AsyncMock(return_value=b""),
    )


def test_video_attachment_detects_video_files():
    assert is_video_attachment(attachment(filename="clip.mp4", content_type="video/mp4")) is True
    assert is_video_attachment(attachment(filename="clip.webm", content_type=None)) is True
    assert is_video_attachment(attachment(filename="photo.png", content_type="image/png")) is False


def test_scam_detector_is_loaded_by_default():
    assert "cogs.scam_image_detector" in DEFAULT_COGS


def test_visual_attachment_detects_images_and_gifs():
    assert is_visual_attachment(attachment(filename="giveaway.gif", content_type="image/gif")) is True
    assert is_visual_attachment(attachment(filename="photo.webp", content_type=None)) is True
    assert is_visual_attachment(attachment(filename="notes.txt", content_type="text/plain")) is False


def test_visual_url_detects_direct_images_and_gifs():
    assert is_visual_url("https://example.com/giveaway.gif") is True
    assert is_visual_url("https://media.discordapp.net/attachments/1/2/image.png?width=800") is True
    assert is_visual_url("https://example.com/page") is False


def test_joke_mrbeast_image_stays_below_alert_threshold():
    assessment = assess_scam_text(
        "rough hand drawn meme of Mr Beast with +200 and continue button",
        has_visual_attachment=True,
    )

    assert assessment.score < ALERT_THRESHOLD
    assert assessment.should_alert is False


def test_realistic_mrbeast_claim_scam_alerts():
    assessment = assess_scam_text(
        "MrBeast giveaway! Claim your free $500 prize now and verify at https://bit.ly/fake",
        has_visual_attachment=True,
    )

    assert assessment.should_alert is True
    assert assessment.level == "high"
    assert "contains a link or suspicious domain" in assessment.reasons


def test_ocr_mrbeast_claim_scam_alerts_without_message_text():
    assessment = assess_scam_text(
        "MrBeast everyone that visits our page gets $500 register claim reward",
        has_visual_attachment=True,
    )

    assert assessment.should_alert is True


def test_mrbeast_free_money_page_ad_alerts_without_url():
    assessment = assess_scam_text(
        "Ad MRBEAST everyone that visits our page gets $500 You're eligible for free $500",
        has_visual_attachment=True,
    )

    assert assessment.should_alert is True


def test_nsfw_visual_detection_alerts():
    assessment = assess_scam_text(
        "",
        has_visual_attachment=True,
        nsfw_detections=("FEMALE_BREAST_EXPOSED (0.91)",),
    )

    assert assessment.should_alert is True
    assert "detects explicit or adult visual content" in assessment.reasons


def test_qr_claim_scam_alerts_even_without_link_text():
    assessment = assess_scam_text(
        "Scan QR to claim free Nitro reward",
        has_qr=True,
        has_visual_attachment=True,
    )

    assert assessment.should_alert is True


def test_detector_is_enabled_only_for_target_bot_id():
    target_bot_id = next(iter(DEFAULT_ENABLED_BOT_IDS))

    assert ScamImageDetector(SimpleNamespace(user=SimpleNamespace(id=target_bot_id))).is_enabled_for_current_bot()
    assert not ScamImageDetector(SimpleNamespace(user=SimpleNamespace(id=123))).is_enabled_for_current_bot()


def test_detector_can_be_enabled_for_configured_application_id():
    bot = SimpleNamespace(
        user=SimpleNamespace(id=456),
        config=SimpleNamespace(get=lambda key, default=None: 456 if key == "application_id" else default),
    )

    assert ScamImageDetector(bot).is_enabled_for_current_bot()


def test_detector_can_be_forced_on_for_standalone_safety_bot():
    bot = SimpleNamespace(user=SimpleNamespace(id=123), scam_detector_always_enabled=True)

    assert ScamImageDetector(bot).is_enabled_for_current_bot()


def test_on_message_forwards_alert_without_ping_or_deletion():
    review_channel = SimpleNamespace(id=REVIEW_CHANNEL_ID, send=AsyncMock())
    bot = SimpleNamespace(
        user=SimpleNamespace(id=next(iter(DEFAULT_ENABLED_BOT_IDS))),
        get_channel=lambda channel_id: review_channel if channel_id == REVIEW_CHANNEL_ID else None,
    )
    cog = ScamImageDetector(bot)
    cog.scan_attachment = AsyncMock(return_value=("", False, ()))

    logs_channel = SimpleNamespace(name="logs", send=AsyncMock())
    message_channel = SimpleNamespace(id=123, name="general", mention="#general", send=AsyncMock())
    guild = SimpleNamespace(id=1, text_channels=[logs_channel])
    message = SimpleNamespace(
        guild=guild,
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=message_channel,
        content="MrBeast giveaway! Claim your free $500 prize now and verify at https://bit.ly/fake",
        attachments=[attachment()],
        jump_url="https://discord.com/channels/1/2/3",
        delete=AsyncMock(),
    )

    asyncio.run(cog.on_message(message))

    review_channel.send.assert_awaited_once()
    assert review_channel.send.await_args.kwargs["content"] is None
    assert review_channel.send.await_args.kwargs["allowed_mentions"].users is False
    assert review_channel.send.await_args.kwargs["embed"].title == "Possible Unsafe Message Detected"
    logs_channel.send.assert_not_awaited()
    message_channel.send.assert_not_awaited()
    message.delete.assert_not_awaited()


def test_on_message_ignores_low_risk_joke_image():
    bot = SimpleNamespace(user=SimpleNamespace(id=next(iter(DEFAULT_ENABLED_BOT_IDS))))
    cog = ScamImageDetector(bot)
    cog.scan_attachment = AsyncMock(return_value=("", False, ()))

    logs_channel = SimpleNamespace(name="logs", send=AsyncMock())
    message_channel = SimpleNamespace(id=123, name="general", mention="#general", send=AsyncMock())
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1, text_channels=[logs_channel]),
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=message_channel,
        content="rough hand drawn meme of Mr Beast with +200 and continue button",
        attachments=[attachment(filename="joke.png")],
        jump_url="https://discord.com/channels/1/2/3",
    )

    asyncio.run(cog.on_message(message))

    logs_channel.send.assert_not_awaited()
    message_channel.send.assert_not_awaited()


def test_on_message_ignores_messages_when_running_on_other_bot():
    bot = SimpleNamespace(user=SimpleNamespace(id=123))
    cog = ScamImageDetector(bot)
    cog.scan_attachment = AsyncMock(return_value=("", False, ()))

    logs_channel = SimpleNamespace(name="logs", send=AsyncMock())
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1, text_channels=[logs_channel]),
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=SimpleNamespace(name="general", mention="#general", send=AsyncMock()),
        content="MrBeast giveaway! Claim your free $500 prize now and verify at https://bit.ly/fake",
        attachments=[attachment()],
        jump_url="https://discord.com/channels/1/2/3",
    )

    asyncio.run(cog.on_message(message))

    logs_channel.send.assert_not_awaited()


def test_on_message_ignores_the_review_channel():
    bot = SimpleNamespace(user=SimpleNamespace(id=next(iter(DEFAULT_ENABLED_BOT_IDS))), get_channel=lambda _: None)
    cog = ScamImageDetector(bot)
    cog.assess_message = AsyncMock()
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=SimpleNamespace(id=REVIEW_CHANNEL_ID),
    )

    asyncio.run(cog.on_message(message))

    cog.assess_message.assert_not_awaited()


def test_attachment_cdn_url_does_not_make_giveaway_joke_high_risk():
    bot = SimpleNamespace()
    cog = ScamImageDetector(bot)
    cog.scan_attachment = AsyncMock(return_value=("", False, ()))

    message = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        content="MrBeast free $200 continue meme",
        attachments=[attachment(url="https://cdn.discordapp.com/attachments/1/2/image.png")],
    )

    assessment = asyncio.run(cog.assess_message(message))

    assert assessment is not None
    assert assessment.score < ALERT_THRESHOLD


def test_ocr_attachment_text_makes_visual_message_dangerous():
    bot = SimpleNamespace()
    cog = ScamImageDetector(bot)
    cog.scan_attachment = AsyncMock(
        return_value=("MrBeast everyone that visits our page gets $500 register claim reward", False, ())
    )

    message = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        content="",
        attachments=[attachment(filename="screenshot.png")],
    )

    assessment = asyncio.run(cog.assess_message(message))

    assert assessment is not None
    assert assessment.should_alert is True


def test_direct_image_link_counts_as_visual_message():
    bot = SimpleNamespace()
    cog = ScamImageDetector(bot)
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        content="MrBeast giveaway claim $500 verify now https://example.xyz/free.png",
        attachments=[],
        embeds=[],
    )

    assessment = asyncio.run(cog.assess_message(message))

    assert assessment is not None
    assert assessment.should_alert is True


def test_plain_scam_text_is_forwarded_without_source_channel_marker():
    review_channel = SimpleNamespace(id=REVIEW_CHANNEL_ID, send=AsyncMock())
    bot = SimpleNamespace(
        user=SimpleNamespace(id=next(iter(DEFAULT_ENABLED_BOT_IDS))),
        get_channel=lambda channel_id: review_channel if channel_id == REVIEW_CHANNEL_ID else None,
    )
    cog = ScamImageDetector(bot)

    logs_channel = SimpleNamespace(name="logs", send=AsyncMock())
    message_channel = SimpleNamespace(id=123, name="general", mention="#general", send=AsyncMock())
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1, text_channels=[logs_channel]),
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=message_channel,
        content="MrBeast giveaway! Claim your free $500 prize now and verify at https://bit.ly/fake",
        attachments=[],
        embeds=[],
        jump_url="https://discord.com/channels/1/2/3",
    )

    asyncio.run(cog.on_message(message))

    message_channel.send.assert_not_awaited()
    logs_channel.send.assert_not_awaited()
    review_channel.send.assert_awaited_once()
    sent_embed = review_channel.send.await_args.kwargs["embed"]
    assert sent_embed.title == "Possible Unsafe Message Detected"
    assert any(field.name == "Original Text" for field in sent_embed.fields)


def test_normal_plain_text_is_ignored_without_safe_spam():
    bot = SimpleNamespace(user=SimpleNamespace(id=next(iter(DEFAULT_ENABLED_BOT_IDS))))
    cog = ScamImageDetector(bot)

    logs_channel = SimpleNamespace(name="logs", send=AsyncMock())
    message_channel = SimpleNamespace(name="general", mention="#general", send=AsyncMock())
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1, text_channels=[logs_channel]),
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=message_channel,
        content="Does anyone know when the next assignment is due?",
        attachments=[],
        embeds=[],
        jump_url="https://discord.com/channels/1/2/3",
    )

    asyncio.run(cog.on_message(message))

    message_channel.send.assert_not_awaited()
    logs_channel.send.assert_not_awaited()


def test_safe_video_does_not_post_a_marker_or_alert():
    bot = SimpleNamespace(user=SimpleNamespace(id=next(iter(DEFAULT_ENABLED_BOT_IDS))))
    cog = ScamImageDetector(bot)
    cog.scan_video_attachment = AsyncMock(return_value=("", False, ()))

    logs_channel = SimpleNamespace(name="logs", send=AsyncMock())
    message_channel = SimpleNamespace(id=123, name="general", mention="#general", send=AsyncMock())
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1, text_channels=[logs_channel]),
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=message_channel,
        content="",
        attachments=[attachment(filename="clip.mp4", content_type="video/mp4")],
        embeds=[],
        jump_url="https://discord.com/channels/1/2/3",
    )

    asyncio.run(cog.on_message(message))

    message_channel.send.assert_not_awaited()
    logs_channel.send.assert_not_awaited()


def test_explicit_video_is_forwarded_without_source_channel_marker():
    review_channel = SimpleNamespace(id=REVIEW_CHANNEL_ID, send=AsyncMock())
    bot = SimpleNamespace(
        user=SimpleNamespace(id=next(iter(DEFAULT_ENABLED_BOT_IDS))),
        get_channel=lambda channel_id: review_channel if channel_id == REVIEW_CHANNEL_ID else None,
    )
    cog = ScamImageDetector(bot)
    cog.scan_video_attachment = AsyncMock(return_value=("", False, ("FEMALE_GENITALIA_EXPOSED (0.93)",)))

    logs_channel = SimpleNamespace(name="logs", send=AsyncMock())
    message_channel = SimpleNamespace(id=123, name="general", mention="#general", send=AsyncMock())
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1, text_channels=[logs_channel]),
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=message_channel,
        content="",
        attachments=[attachment(filename="clip.mp4", content_type="video/mp4")],
        embeds=[],
        jump_url="https://discord.com/channels/1/2/3",
    )

    asyncio.run(cog.on_message(message))

    message_channel.send.assert_not_awaited()
    logs_channel.send.assert_not_awaited()
    review_channel.send.assert_awaited_once()


def test_dangerous_message_forwards_to_fixed_review_channel():
    review_channel = SimpleNamespace(id=REVIEW_CHANNEL_ID, name="scam-review", send=AsyncMock())
    logs_channel = SimpleNamespace(name="logs", send=AsyncMock())
    bot = SimpleNamespace(
        user=SimpleNamespace(id=next(iter(DEFAULT_ENABLED_BOT_IDS))),
        get_channel=lambda channel_id: review_channel if channel_id == REVIEW_CHANNEL_ID else None,
    )
    cog = ScamImageDetector(bot)
    cog.scan_video_attachment = AsyncMock(return_value=("", False, ("MALE_GENITALIA_EXPOSED (0.93)",)))

    message_channel = SimpleNamespace(id=123, name="general", mention="#general", send=AsyncMock())
    message = SimpleNamespace(
        guild=SimpleNamespace(id=1, text_channels=[logs_channel]),
        author=SimpleNamespace(id=111, mention="<@111>", bot=False),
        channel=message_channel,
        content="",
        attachments=[attachment(filename="clip.mp4", content_type="video/mp4", url="https://cdn.discordapp.com/clip.mp4")],
        embeds=[],
        jump_url="https://discord.com/channels/1/2/3",
    )

    asyncio.run(cog.on_message(message))

    review_channel.send.assert_awaited_once()
    logs_channel.send.assert_not_awaited()
    sent_embed = review_channel.send.await_args.kwargs["embed"]
    assert any("clip.mp4" in field.value for field in sent_embed.fields if field.name == "Attachments")


def test_dm_for_money_scam_text_alerts():
    assessment = assess_scam_text(
        "Hello! My name is Push and I'm giving away 200 THOUSAND dollars to the first person who DMs me!",
        has_visual_attachment=False,
        content_kind="text",
    )

    assert assessment.should_alert is True
    assert assessment.content_kind == "text"


def test_free_nitro_dm_scam_alerts():
    assessment = assess_scam_text("Free Nitro! DM me to claim", has_visual_attachment=False)

    assert assessment.should_alert is True


def test_dm_me_homework_is_ignored():
    assessment = assess_scam_text("hey can you dm me your homework notes", has_visual_attachment=False)

    assert assessment.score < REVIEW_THRESHOLD
    assert assessment.should_alert is False


def test_first_to_finish_is_not_an_alert():
    assessment = assess_scam_text("first person to finish the quiz gets a gold star", has_visual_attachment=False)

    assert assessment.should_alert is False


def test_get_rich_offsite_telegram_scam_alerts():
    assessment = assess_scam_text(
        "Hello, are you looking to get rich! Just go to push.com or DM me on telegram at @pushh for a chance to win one million dollars!",
        has_visual_attachment=False,
        content_kind="text",
    )

    assert assessment.should_alert is True


def test_million_dollars_spelled_out_counts_as_money():
    assessment = assess_scam_text("win one million dollars, dm me now", has_visual_attachment=False)

    assert assessment.should_alert is True
