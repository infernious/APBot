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

from cogs.moderation.commands import validate_selfmute_duration


def test_validate_selfmute_duration_accepts_bounds():
    assert validate_selfmute_duration("10m") == (600, None)
    assert validate_selfmute_duration("168h") == (604800, None)


def test_validate_selfmute_duration_rejects_out_of_range():
    assert validate_selfmute_duration("9m")[0] is None
    assert validate_selfmute_duration("169h")[0] is None
