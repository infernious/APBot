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

from cogs.moderation.commands import (
    current_timeout_ends_after,
    format_duration_seconds,
    validate_selfmute_duration,
)


def test_validate_selfmute_duration_accepts_bounds():
    assert validate_selfmute_duration("10m") == (600, None)
    assert validate_selfmute_duration("168h") == (604800, None)
    assert validate_selfmute_duration("1w") == (604800, None)


def test_validate_selfmute_duration_rejects_out_of_range():
    assert validate_selfmute_duration("9m")[0] is None
    assert validate_selfmute_duration("169h")[0] is None


def test_current_timeout_ends_after_prevents_shortening_existing_timeout():
    unmute_time = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    member = SimpleNamespace(communication_disabled_until=datetime(2026, 5, 25, 13, 0, tzinfo=timezone.utc))

    assert current_timeout_ends_after(member, unmute_time) is True


def test_current_timeout_ends_after_allows_longer_selfmute():
    unmute_time = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)
    member = SimpleNamespace(communication_disabled_until=datetime(2026, 5, 25, 11, 0, tzinfo=timezone.utc))

    assert current_timeout_ends_after(member, unmute_time) is False


def test_format_duration_seconds():
    assert format_duration_seconds(600) == "10m"
    assert format_duration_seconds(604800) == "7d"
    assert format_duration_seconds(90061) == "1d 1h 1m 1s"
