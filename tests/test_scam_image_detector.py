import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cogs.scam_image_detector import (
    ALERT_THRESHOLD,
    MODERATION_BYPASS_ROLE_IDS,
    REVIEW_CHANNEL_ID,
    TARGET_APPLICATION_ID,
    ScamAssessment,
    ScamImageDetector,
    assess_scam_text,
    has_moderation_bypass_role,
    is_audio_attachment,
    is_video_attachment,
    is_visual_attachment,
)
from startup import DEFAULT_COGS


def attachment(filename, content_type):
    return SimpleNamespace(filename=filename, content_type=content_type)


def dangerous_assessment():
    return ScamAssessment(
        score=90,
        reasons=("test danger",),
        scanned_text="dangerous text",
        content_kind="text",
    )


def make_message(channel_id=123, roles=None):
    channel = SimpleNamespace(id=channel_id, mention=f"<#{channel_id}>", send=AsyncMock())
    author = SimpleNamespace(id=456, mention="<@456>", bot=False, roles=roles or [])
    return SimpleNamespace(
        id=789,
        guild=SimpleNamespace(id=1),
        author=author,
        channel=channel,
        content="unsafe message",
        attachments=[],
        embeds=[],
        reference=None,
        jump_url="https://discord.com/channels/1/123/789",
    )


def make_bot(user_id=TARGET_APPLICATION_ID):
    review_channel = SimpleNamespace(id=REVIEW_CHANNEL_ID, send=AsyncMock())
    bot = SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        get_channel=lambda channel_id: review_channel if channel_id == REVIEW_CHANNEL_ID else None,
        fetch_channel=AsyncMock(return_value=review_channel),
        http=SimpleNamespace(),
    )
    return bot, review_channel


def test_cog_is_loaded_by_default():
    assert "cogs.scam_image_detector" in DEFAULT_COGS


def test_target_ids_match_requested_bot_and_review_channel():
    assert TARGET_APPLICATION_ID == 1508281890820460604
    assert REVIEW_CHANNEL_ID == 1508284501485162541


def test_media_types_include_images_gifs_videos_and_voice_memos():
    assert is_visual_attachment(attachment("image.png", "image/png"))
    assert is_visual_attachment(attachment("animation.gif", "image/gif"))
    assert is_video_attachment(attachment("clip.mp4", "video/mp4"))
    assert is_audio_attachment(attachment("voice-message.ogg", "audio/ogg"))


def test_discord_invite_links_are_not_moderated():
    assessment = assess_scam_text(
        "join my server at https://discord.gg/example",
        has_media=False,
        content_kind="text",
    )

    assert assessment.score < ALERT_THRESHOLD
    assert not assessment.should_alert


def test_genuine_scam_text_still_alerts():
    assessment = assess_scam_text(
        "MrBeast giveaway claim your free $500 at https://example.xyz/login",
        has_media=False,
        content_kind="text",
    )

    assert assessment.should_alert


def test_withdrawal_code_purchase_scam_alerts():
    assessment = assess_scam_text(
        "purchase the private bank code for $57 to complete your withdrawal process",
        has_media=True,
        content_kind="image",
    )

    assert assessment.should_alert


def test_trusted_roles_bypass_moderation():
    role_id = next(iter(MODERATION_BYPASS_ROLE_IDS))
    member = SimpleNamespace(roles=[SimpleNamespace(id=role_id)])

    assert has_moderation_bypass_role(member)


def test_wrong_application_id_does_not_scan():
    bot, review_channel = make_bot(user_id=1)
    cog = ScamImageDetector(bot)
    cog.assess_message = AsyncMock(return_value=(dangerous_assessment(), []))

    asyncio.run(cog.handle_message(make_message()))

    cog.assess_message.assert_not_awaited()
    review_channel.send.assert_not_awaited()


def test_trusted_role_does_not_scan():
    bot, review_channel = make_bot()
    cog = ScamImageDetector(bot)
    cog.assess_message = AsyncMock(return_value=(dangerous_assessment(), []))
    role_id = next(iter(MODERATION_BYPASS_ROLE_IDS))

    asyncio.run(cog.handle_message(make_message(roles=[SimpleNamespace(id=role_id)])))

    cog.assess_message.assert_not_awaited()
    review_channel.send.assert_not_awaited()


def test_review_channel_messages_are_not_scanned_or_forwarded():
    bot, review_channel = make_bot()
    cog = ScamImageDetector(bot)
    cog.assess_message = AsyncMock(return_value=(dangerous_assessment(), []))

    asyncio.run(cog.handle_message(make_message(channel_id=REVIEW_CHANNEL_ID)))

    cog.assess_message.assert_not_awaited()
    review_channel.send.assert_not_awaited()


def test_unsafe_message_from_any_channel_forwards_to_review_channel():
    bot, review_channel = make_bot()
    cog = ScamImageDetector(bot)
    cog.assess_message = AsyncMock(return_value=(dangerous_assessment(), []))
    message = make_message(channel_id=999)

    asyncio.run(cog.handle_message(message))

    cog.assess_message.assert_awaited_once_with(message)
    review_channel.send.assert_awaited_once()
    message.channel.send.assert_not_awaited()
    assert review_channel.send.await_args.kwargs["content"] == "<@920819377627099166>"


def test_safe_message_is_forwarded_without_alert_ping():
    bot, review_channel = make_bot()
    cog = ScamImageDetector(bot)
    cog.assess_message = AsyncMock(return_value=(None, []))

    asyncio.run(cog.handle_message(make_message(channel_id=999)))

    review_channel.send.assert_awaited_once()
    assert review_channel.send.await_args.kwargs["content"] is None
    assert review_channel.send.await_args.kwargs["embed"].title == "Server Message"
