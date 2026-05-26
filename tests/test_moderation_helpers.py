import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cogs.moderation.commands import ModerationCommands
from cogs.moderation.infraction import Infraction as InfractionCog
from cogs.moderation.infraction import can_embed_image
from cogs.moderation.infraction import format_action_name
from cogs.moderation.infraction import format_attachment_line
from cogs.moderation.infraction import format_duration
from cogs.moderation.infraction import format_infraction_updates
from cogs.moderation.infraction import to_snowflake


def test_moderation_commands_has_mod_role_accepts_admin_and_moderator():
    cog = ModerationCommands(bot=object())

    assert cog.has_mod_role(SimpleNamespace(roles=[SimpleNamespace(name="Admin")])) is True
    assert cog.has_mod_role(SimpleNamespace(roles=[SimpleNamespace(name="Moderator")])) is True
    assert cog.has_mod_role(SimpleNamespace(roles=[SimpleNamespace(name="Member")])) is False


def test_infraction_cog_has_mod_role_matches_expected_roles():
    cog = InfractionCog(bot=object())

    assert cog.has_mod_role(SimpleNamespace(roles=[SimpleNamespace(name="Chat Moderator")])) is True
    assert cog.has_mod_role(SimpleNamespace(roles=[SimpleNamespace(name="Trial Chat Moderator")])) is True
    assert cog.has_mod_role(SimpleNamespace(roles=[SimpleNamespace(name="Student")])) is False


def test_to_snowflake_parses_mentions_and_ints():
    assert to_snowflake(123456789012345678) == 123456789012345678
    assert to_snowflake("<@123456789012345678>") == 123456789012345678
    assert to_snowflake("not-a-user") is None
    assert to_snowflake(None) is None


def test_to_snowflake_recovers_legacy_ids_with_extra_digits():
    assert to_snowflake("7079852600207606280") == 707985260020760628
    assert to_snowflake("1002335003411222638140") == 1002335003411222638


def test_resolve_moderator_fetches_member_when_not_cached():
    moderator = SimpleNamespace(
        id=707985260020760628,
        mention="<@707985260020760628>",
        display_name="Senior Mod",
        name="senior-mod",
    )
    guild = SimpleNamespace(
        get_member=lambda user_id: None,
        fetch_member=AsyncMock(return_value=moderator),
    )
    bot = SimpleNamespace(
        get_user=lambda user_id: None,
        fetch_user=AsyncMock(return_value=None),
    )
    cog = InfractionCog(bot=bot)

    resolved, moderator_id = asyncio.run(cog.resolve_moderator(guild, "7079852600207606280"))

    assert resolved is moderator
    assert moderator_id == 707985260020760628
    guild.fetch_member.assert_awaited_once_with(707985260020760628)


def test_format_infraction_updates_shows_note_moderator_and_date():
    text = format_infraction_updates([
        {
            "moderator": 123456789012345678,
            "update": "extra context",
            "date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        }
    ])

    assert "Notes:" in text
    assert "extra context" in text
    assert "<@123456789012345678>" in text


def test_warning_display_helpers_format_legacy_details():
    assert format_action_name("force-ban") == "Force Ban"
    assert format_action_name("note") == "Internal Note"
    assert format_duration(timedelta(hours=1, minutes=30)) == "1h 30m"
    assert format_duration(0) is None
    assert format_attachment_line("https://example.com/evidence.png") == (
        "Evidence: [View attachment](https://example.com/evidence.png)\n"
    )
    assert can_embed_image("https://example.com/evidence.png?size=1024") is True
    assert can_embed_image("https://example.com/evidence.txt") is False
