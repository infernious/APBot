from datetime import datetime, timezone
from types import SimpleNamespace

from cogs.moderation.commands import ModerationCommands
from cogs.moderation.infraction import Infraction as InfractionCog
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

from datetime import datetime, timezone
from cogs.moderation.infraction import format_infraction_updates


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
