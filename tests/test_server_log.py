import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import nextcord
import pytest

from cogs.server_log import base, member_events
from cogs.server_log.base import (
    audit_touched,
    diff_permissions,
    find_audit_entry,
    format_role_list,
    resolve_log_channel,
)
from cogs.server_log.channel_events import ChannelLog, diff_overwrite, overwrite_map
from cogs.server_log.emoji_events import EmojiLog
from cogs.server_log.invite_events import InviteLog
from cogs.server_log.member_events import MemberLog, humanize_delta
from cogs.server_log.mod_command_events import (
    ModCommandLog,
    format_option_value,
    leaf_options,
    resolve_command_name,
)
from cogs.server_log.role_events import RoleLog
from startup import DEFAULT_COGS


GUILD_ID = 777
OTHER_GUILD_ID = 888
LOG_CHANNEL_ID = 5000

SERVER_LOG_COGS = (
    "cogs.server_log.member_events",
    "cogs.server_log.role_events",
    "cogs.server_log.channel_events",
    "cogs.server_log.emoji_events",
    "cogs.server_log.invite_events",
    "cogs.server_log.mod_command_events",
)


@pytest.fixture(autouse=True)
def instant_audit_retries(monkeypatch):
    """Keeps the audit-log retry and ban-grace waits from making the suite crawl."""
    monkeypatch.setattr(base, "AUDIT_RETRY_DELAY", 0)
    monkeypatch.setattr(member_events, "BAN_GRACE_SECONDS", 0)


# ----------------------------------------------------------------------
# Fakes
# ----------------------------------------------------------------------


class FakeAuditLogs:
    def __init__(self, entries, action):
        # action=None mirrors Discord returning every recent entry.
        self.entries = [entry for entry in entries if action is None or entry.action == action]

    def __aiter__(self):
        async def generator():
            for entry in self.entries:
                yield entry

        return generator()


def audit_entry(action, user=None, target=None, reason=None, age_seconds=1):
    return SimpleNamespace(
        action=action,
        user=user,
        target=target,
        reason=reason,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
        extra=None,
    )


def fake_guild(
    *,
    guild_id=GUILD_ID,
    channels=None,
    audit_entries=None,
    view_audit_log=True,
    members=None,
    member_count=100,
):
    entries = audit_entries or []

    guild = SimpleNamespace(
        id=guild_id,
        name="AP Students",
        text_channels=channels or [],
        members=members or [],
        member_count=member_count,
        me=SimpleNamespace(guild_permissions=SimpleNamespace(view_audit_log=view_audit_log)),
    )
    guild.get_channel = lambda channel_id: next(
        (channel for channel in guild.text_channels if channel.id == channel_id), None
    )
    guild.get_member = lambda member_id: next(
        (member for member in guild.members if member.id == member_id), None
    )
    guild.audit_logs = lambda limit=None, action=None: FakeAuditLogs(entries, action)
    return guild


def log_channel(channel_id=LOG_CHANNEL_ID, name="server-log"):
    return SimpleNamespace(id=channel_id, name=name, send=AsyncMock())


def fake_bot(config=None, channel=None, guild=None):
    values = {"guild_id": GUILD_ID, "server_log_channel_id": LOG_CHANNEL_ID}
    values.update(config or {})

    return SimpleNamespace(
        config=SimpleNamespace(get=values.get),
        colors={},
        get_channel=lambda channel_id: channel if channel and channel.id == channel_id else None,
        get_guild=lambda guild_id: guild if guild and guild.id == guild_id else None,
        fetch_invite=AsyncMock(),
    )


class FakeRole(SimpleNamespace):
    """Hashable so it can key a channel's `overwrites` dict like a real Role."""

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return getattr(other, "id", None) == self.id


def make_role(role_id, name, position=1, color_value=0, permissions=None, members=None):
    return FakeRole(
        id=role_id,
        name=name,
        position=position,
        mention=f"<@&{role_id}>",
        color=SimpleNamespace(value=color_value),
        permissions=permissions or nextcord.Permissions.none(),
        hoist=False,
        mentionable=False,
        members=members or [],
        guild=None,
    )


def make_member(member_id=1, name="pushi", roles=None, nick=None, timeout_until=None, guild=None, bot=False):
    return SimpleNamespace(
        id=member_id,
        name=name,
        display_name=nick or name,
        mention=f"<@{member_id}>",
        bot=bot,
        nick=nick,
        roles=roles if roles is not None else [],
        guild=guild,
        display_avatar=SimpleNamespace(url="https://cdn.discordapp.com/avatars/1/a.png"),
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        joined_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
        communication_disabled_until=timeout_until,
    )


def sent_embeds(channel):
    return [call.kwargs["embed"] for call in channel.send.await_args_list]


def only_embed(channel):
    assert channel.send.await_count == 1
    return sent_embeds(channel)[0]


def field_value(embed, name):
    return next(field.value for field in embed.fields if field.name == name)


def field_names(embed):
    return [field.name for field in embed.fields]


# ----------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------


@pytest.mark.parametrize("extension", SERVER_LOG_COGS)
def test_server_log_cogs_are_loaded_by_default(extension):
    assert extension in DEFAULT_COGS


# ----------------------------------------------------------------------
# Channel resolution
# ----------------------------------------------------------------------


def test_resolve_log_channel_prefers_configured_id():
    channel = log_channel(name="anything")
    guild = fake_guild(channels=[channel])

    assert resolve_log_channel(fake_bot(channel=channel), guild) is channel


def test_resolve_log_channel_falls_back_to_named_channel():
    named = log_channel(channel_id=42, name="server-log")
    guild = fake_guild(channels=[named])
    bot = fake_bot(config={"server_log_channel_id": None})

    assert resolve_log_channel(bot, guild) is named


def test_resolve_log_channel_falls_back_when_configured_id_is_unresolvable():
    named = log_channel(channel_id=42, name="server-log")
    guild = fake_guild(channels=[named])
    bot = fake_bot(config={"server_log_channel_id": 999999})

    assert resolve_log_channel(bot, guild) is named


def test_resolve_log_channel_returns_none_when_nothing_matches():
    guild = fake_guild(channels=[])
    bot = fake_bot(config={"server_log_channel_id": None})

    assert resolve_log_channel(bot, guild) is None


def test_send_log_skips_other_guilds():
    channel = log_channel()
    guild = fake_guild(guild_id=OTHER_GUILD_ID, channels=[channel])
    cog = RoleLog(fake_bot(channel=channel))

    asyncio.run(cog.send_log(guild, nextcord.Embed(title="x")))

    channel.send.assert_not_awaited()


# ----------------------------------------------------------------------
# Audit log correlation
# ----------------------------------------------------------------------


def test_find_audit_entry_matches_recent_entry_for_target():
    actor = make_member(member_id=9, name="mod")
    entry = audit_entry(nextcord.AuditLogAction.kick, user=actor, target=SimpleNamespace(id=1))
    guild = fake_guild(audit_entries=[entry])

    found = asyncio.run(find_audit_entry(guild, nextcord.AuditLogAction.kick, target_id=1, attempts=1))

    assert found is entry


def test_find_audit_entry_ignores_stale_entries():
    entry = audit_entry(
        nextcord.AuditLogAction.kick,
        target=SimpleNamespace(id=1),
        age_seconds=600,
    )
    guild = fake_guild(audit_entries=[entry])

    found = asyncio.run(find_audit_entry(guild, nextcord.AuditLogAction.kick, target_id=1, attempts=1))

    assert found is None


def test_find_audit_entry_ignores_other_targets():
    entry = audit_entry(nextcord.AuditLogAction.kick, target=SimpleNamespace(id=2))
    guild = fake_guild(audit_entries=[entry])

    found = asyncio.run(find_audit_entry(guild, nextcord.AuditLogAction.kick, target_id=1, attempts=1))

    assert found is None


def test_find_audit_entry_requires_view_audit_log_permission():
    entry = audit_entry(nextcord.AuditLogAction.kick, target=SimpleNamespace(id=1))
    guild = fake_guild(audit_entries=[entry], view_audit_log=False)

    found = asyncio.run(find_audit_entry(guild, nextcord.AuditLogAction.kick, target_id=1, attempts=1))

    assert found is None


# ----------------------------------------------------------------------
# Formatting helpers
# ----------------------------------------------------------------------


def test_format_role_list_orders_by_position_and_drops_everyone():
    roles = [
        make_role(1, "@everyone", position=0),
        make_role(2, "Member", position=1),
        make_role(3, "Moderator", position=5),
    ]

    assert format_role_list(roles) == "<@&3>, <@&2>"


def test_format_role_list_handles_no_roles():
    assert format_role_list([make_role(1, "@everyone", position=0)]) == "None"


def test_humanize_delta_formats_two_largest_units():
    assert humanize_delta(45) == "45s"
    assert humanize_delta(3600 + 120) == "1h 2m"
    assert humanize_delta(86400 * 2 + 3600 * 3) == "2d 3h"


def test_diff_permissions_reports_both_directions():
    before = nextcord.Permissions(send_messages=True)
    after = nextcord.Permissions(manage_messages=True)

    granted, revoked = diff_permissions(before, after)

    assert "manage_messages" in granted
    assert "send_messages" in revoked


# ----------------------------------------------------------------------
# Member events
# ----------------------------------------------------------------------


def test_member_join_logs_account_age_and_flags_new_accounts():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    member = make_member(guild=guild)
    member.created_at = datetime.now(timezone.utc) - timedelta(days=1)

    cog = MemberLog(fake_bot(channel=channel))
    asyncio.run(cog.on_member_join(member))

    embed = only_embed(channel)
    assert embed.title == "Member Joined"
    assert "⚠️ New Account" in field_names(embed)
    assert field_value(embed, "Member Count") == "`100`"


def test_member_leave_lists_roles_held():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    member = make_member(guild=guild, roles=[make_role(1, "@everyone", 0), make_role(2, "Helper", 3)])

    cog = MemberLog(fake_bot(channel=channel))
    asyncio.run(cog.on_member_remove(member))

    embed = only_embed(channel)
    assert embed.title == "Member Left"
    assert field_value(embed, "Roles Held") == "<@&2>"


def test_member_leave_reported_as_kick_when_audit_log_shows_one():
    channel = log_channel()
    mod = make_member(member_id=9, name="mod")
    guild = fake_guild(
        channels=[channel],
        audit_entries=[
            audit_entry(
                nextcord.AuditLogAction.kick,
                user=mod,
                target=SimpleNamespace(id=1),
                reason="spam",
            )
        ],
    )
    member = make_member(guild=guild)

    cog = MemberLog(fake_bot(channel=channel))
    asyncio.run(cog.on_member_remove(member))

    embed = only_embed(channel)
    assert embed.title == "Member Kicked"
    assert "<@9>" in field_value(embed, "Kicked By")
    assert field_value(embed, "Reason") == "spam"


def test_member_leave_is_suppressed_when_the_member_was_banned():
    channel = log_channel()
    guild = fake_guild(
        channels=[channel],
        audit_entries=[audit_entry(nextcord.AuditLogAction.ban, target=SimpleNamespace(id=1))],
    )
    member = make_member(guild=guild)

    cog = MemberLog(fake_bot(channel=channel))
    asyncio.run(cog.on_member_remove(member))

    channel.send.assert_not_awaited()


def test_member_leave_is_suppressed_when_the_ban_event_arrives_first():
    """The ban event can beat the audit log, so the cog remembers recent bans."""
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    member = make_member(guild=guild)
    cog = MemberLog(fake_bot(channel=channel))

    async def run():
        await cog.on_member_ban(guild, member)
        channel.send.reset_mock()
        await cog.on_member_remove(member)

    asyncio.run(run())

    channel.send.assert_not_awaited()


def test_audit_touched_filters_unrelated_member_updates():
    nick_only = SimpleNamespace(
        changes=SimpleNamespace(
            before=SimpleNamespace(nick="old"),
            after=SimpleNamespace(nick="new"),
        )
    )

    assert audit_touched(nick_only, "nick") is True
    assert audit_touched(nick_only, "communication_disabled_until") is False


def test_timeout_actor_is_not_taken_from_a_nickname_audit_entry():
    channel = log_channel()
    nick_entry = audit_entry(
        nextcord.AuditLogAction.member_update,
        user=make_member(member_id=9, name="mod"),
        target=SimpleNamespace(id=1),
    )
    nick_entry.changes = SimpleNamespace(
        before=SimpleNamespace(nick="old"),
        after=SimpleNamespace(nick="new"),
    )
    guild = fake_guild(channels=[channel], audit_entries=[nick_entry])

    before = make_member(guild=guild, timeout_until=datetime.now(timezone.utc) + timedelta(hours=1))
    after = make_member(guild=guild)

    asyncio.run(MemberLog(fake_bot(channel=channel)).on_member_update(before, after))

    # The only candidate entry was a nickname edit, so no removal is claimed.
    channel.send.assert_not_awaited()


def test_member_ban_logs_moderator_and_reason():
    channel = log_channel()
    mod = make_member(member_id=9, name="mod")
    guild = fake_guild(
        channels=[channel],
        audit_entries=[
            audit_entry(
                nextcord.AuditLogAction.ban,
                user=mod,
                target=SimpleNamespace(id=1),
                reason="raiding",
            )
        ],
    )

    cog = MemberLog(fake_bot(channel=channel))
    asyncio.run(cog.on_member_ban(guild, make_member(guild=guild)))

    embed = only_embed(channel)
    assert embed.title == "Member Banned"
    assert field_value(embed, "Reason") == "raiding"


def test_member_unban_logs_moderator():
    channel = log_channel()
    guild = fake_guild(
        channels=[channel],
        audit_entries=[
            audit_entry(
                nextcord.AuditLogAction.unban,
                user=make_member(member_id=9, name="mod"),
                target=SimpleNamespace(id=1),
            )
        ],
    )

    cog = MemberLog(fake_bot(channel=channel))
    asyncio.run(cog.on_member_unban(guild, make_member(guild=guild)))

    assert only_embed(channel).title == "Member Unbanned"


def test_role_add_and_remove_emit_separate_embeds():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    everyone = make_role(1, "@everyone", 0)
    helper = make_role(2, "Helper", 3)
    muted = make_role(3, "Muted", 4)

    before = make_member(guild=guild, roles=[everyone, muted])
    after = make_member(guild=guild, roles=[everyone, helper])

    cog = MemberLog(fake_bot(channel=channel))
    asyncio.run(cog.on_member_update(before, after))

    titles = [embed.title for embed in sent_embeds(channel)]
    assert titles == ["Member Role Added", "Member Role Removed"]


def test_role_changes_respect_the_ignored_role_config():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    everyone = make_role(1, "@everyone", 0)
    level_role = make_role(2, "Level 5", 3)

    before = make_member(guild=guild, roles=[everyone])
    after = make_member(guild=guild, roles=[everyone, level_role])

    bot = fake_bot(channel=channel, config={"server_log_ignored_role_ids": [2]})
    asyncio.run(MemberLog(bot).on_member_update(before, after))

    channel.send.assert_not_awaited()


def test_timeout_applied_logs_expiry_and_duration():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    until = datetime.now(timezone.utc) + timedelta(hours=2)

    before = make_member(guild=guild)
    after = make_member(guild=guild, timeout_until=until)

    cog = MemberLog(fake_bot(channel=channel))

    async def run():
        await cog.on_member_update(before, after)
        cog.cog_unload()

    asyncio.run(run())

    embed = only_embed(channel)
    assert embed.title == "Member Timed Out"
    assert "Expires" in field_names(embed)
    assert field_value(embed, "Duration").startswith("`1h 59m")


def test_timeout_removal_is_only_logged_when_a_moderator_did_it():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    before = make_member(guild=guild, timeout_until=datetime.now(timezone.utc) + timedelta(hours=1))
    after = make_member(guild=guild)

    asyncio.run(MemberLog(fake_bot(channel=channel)).on_member_update(before, after))

    # No audit entry means it lapsed naturally; the scheduled task reports that.
    channel.send.assert_not_awaited()


def test_timeout_removal_logs_the_moderator_when_present():
    channel = log_channel()
    guild = fake_guild(
        channels=[channel],
        audit_entries=[
            audit_entry(
                nextcord.AuditLogAction.member_update,
                user=make_member(member_id=9, name="mod"),
                target=SimpleNamespace(id=1),
            )
        ],
    )
    before = make_member(guild=guild, timeout_until=datetime.now(timezone.utc) + timedelta(hours=1))
    after = make_member(guild=guild)

    asyncio.run(MemberLog(fake_bot(channel=channel)).on_member_update(before, after))

    assert only_embed(channel).title == "Member Timeout Removed"


def test_nickname_change_logs_before_and_after():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    before = make_member(guild=guild, nick=None)
    after = make_member(guild=guild, nick="new nick")

    asyncio.run(MemberLog(fake_bot(channel=channel)).on_member_update(before, after))

    embed = only_embed(channel)
    assert embed.title == "Nickname Changed"
    assert field_value(embed, "Before") == "*None*"
    assert field_value(embed, "After") == "new nick"


def test_member_update_without_tracked_changes_is_silent():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    roles = [make_role(1, "@everyone", 0)]

    asyncio.run(
        MemberLog(fake_bot(channel=channel)).on_member_update(
            make_member(guild=guild, roles=roles),
            make_member(guild=guild, roles=roles),
        )
    )

    channel.send.assert_not_awaited()


# ----------------------------------------------------------------------
# Role events
# ----------------------------------------------------------------------


def test_role_create_logs_permissions_and_actor():
    channel = log_channel()
    guild = fake_guild(
        channels=[channel],
        audit_entries=[
            audit_entry(
                nextcord.AuditLogAction.role_create,
                user=make_member(member_id=9, name="admin"),
                target=SimpleNamespace(id=50),
            )
        ],
    )
    role = make_role(50, "New Role", color_value=0xFF0000, permissions=nextcord.Permissions(kick_members=True))
    role.guild = guild

    asyncio.run(RoleLog(fake_bot(channel=channel)).on_guild_role_create(role))

    embed = only_embed(channel)
    assert embed.title == "Role Created"
    assert field_value(embed, "Color") == "`#FF0000`"
    assert "Kick Members" in field_value(embed, "Permissions")


def test_role_delete_logs_member_count():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    role = make_role(50, "Old Role", members=[make_member(), make_member(member_id=2)])
    role.guild = guild

    asyncio.run(RoleLog(fake_bot(channel=channel)).on_guild_role_delete(role))

    embed = only_embed(channel)
    assert embed.title == "Role Deleted"
    assert field_value(embed, "Members With Role") == "`2`"


def test_role_update_logs_color_and_permission_changes():
    channel = log_channel()
    guild = fake_guild(channels=[channel])

    before = make_role(50, "Helper", color_value=0xFF0000, permissions=nextcord.Permissions(send_messages=True))
    after = make_role(50, "Helper", color_value=0x00FF00, permissions=nextcord.Permissions(manage_messages=True))
    before.guild = after.guild = guild

    asyncio.run(RoleLog(fake_bot(channel=channel)).on_guild_role_update(before, after))

    embed = only_embed(channel)
    assert embed.title == "Role Updated"
    assert field_value(embed, "Color") == "`#FF0000` → `#00FF00`"
    assert "Manage Messages" in field_value(embed, "Permissions Granted")
    assert "Send Messages" in field_value(embed, "Permissions Revoked")


def test_role_update_ignores_position_only_changes():
    channel = log_channel()
    guild = fake_guild(channels=[channel])

    before = make_role(50, "Helper", position=1)
    after = make_role(50, "Helper", position=9)
    before.guild = after.guild = guild

    asyncio.run(RoleLog(fake_bot(channel=channel)).on_guild_role_update(before, after))

    channel.send.assert_not_awaited()


# ----------------------------------------------------------------------
# Channel events
# ----------------------------------------------------------------------


def make_channel(channel_id=100, name="general", overwrites=None, **kwargs):
    channel = SimpleNamespace(
        id=channel_id,
        name=name,
        mention=f"<#{channel_id}>",
        type=SimpleNamespace(name="text"),
        category=None,
        overwrites=overwrites or {},
        topic=None,
        nsfw=False,
        slowmode_delay=0,
        guild=None,
    )

    for key, value in kwargs.items():
        setattr(channel, key, value)

    return channel


def test_channel_create_logs_type_and_actor():
    channel = log_channel()
    guild = fake_guild(
        channels=[channel],
        audit_entries=[
            audit_entry(
                nextcord.AuditLogAction.channel_create,
                user=make_member(member_id=9, name="admin"),
                target=SimpleNamespace(id=100),
            )
        ],
    )
    created = make_channel()
    created.guild = guild

    asyncio.run(ChannelLog(fake_bot(channel=channel)).on_guild_channel_create(created))

    embed = only_embed(channel)
    assert embed.title == "Channel Created"
    assert field_value(embed, "Type") == "`Text`"


def test_channel_delete_is_logged():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    deleted = make_channel(name="old-channel")
    deleted.guild = guild

    asyncio.run(ChannelLog(fake_bot(channel=channel)).on_guild_channel_delete(deleted))

    assert only_embed(channel).title == "Channel Deleted"


def test_channel_update_logs_settings_changes():
    channel = log_channel()
    guild = fake_guild(channels=[channel])

    before = make_channel(name="general", slowmode_delay=0)
    after = make_channel(name="general-chat", slowmode_delay=10)
    before.guild = after.guild = guild

    asyncio.run(ChannelLog(fake_bot(channel=channel)).on_guild_channel_update(before, after))

    embed = only_embed(channel)
    assert embed.title == "Channel Updated"
    assert field_value(embed, "Name") == "`general` → `general-chat`"
    assert field_value(embed, "Slowmode") == "`Off` → `10s`"


def test_channel_update_ignores_untracked_changes():
    channel = log_channel()
    guild = fake_guild(channels=[channel])

    before = make_channel(position=1)
    after = make_channel(position=5)
    before.guild = after.guild = guild

    asyncio.run(ChannelLog(fake_bot(channel=channel)).on_guild_channel_update(before, after))

    channel.send.assert_not_awaited()


def test_channel_update_logs_permission_overwrite_changes():
    channel = log_channel()
    guild = fake_guild(channels=[channel])

    role = make_role(2, "Helper")
    before_overwrite = nextcord.PermissionOverwrite(send_messages=True)
    after_overwrite = nextcord.PermissionOverwrite(send_messages=False)

    before = make_channel(overwrites={role: before_overwrite})
    after = make_channel(overwrites={role: after_overwrite})
    before.guild = after.guild = guild

    asyncio.run(ChannelLog(fake_bot(channel=channel)).on_guild_channel_update(before, after))

    embed = only_embed(channel)
    value = field_value(embed, "Permissions Changed — Helper")
    assert "Send Messages" in value
    assert "✅ Allow → ❌ Deny" in value


def test_channel_update_finds_actor_from_overwrite_create_entries():
    channel = log_channel()
    role = make_role(2, "Helper")
    guild = fake_guild(
        channels=[channel],
        audit_entries=[
            audit_entry(
                nextcord.AuditLogAction.overwrite_create,
                user=make_member(member_id=9, name="admin"),
                target=SimpleNamespace(id=100),
            )
        ],
    )

    before = make_channel(overwrites={})
    after = make_channel(overwrites={role: nextcord.PermissionOverwrite(send_messages=False)})
    before.guild = after.guild = guild

    asyncio.run(ChannelLog(fake_bot(channel=channel)).on_guild_channel_update(before, after))

    embed = only_embed(channel)
    assert "<@9>" in field_value(embed, "Updated By")


def test_diff_overwrite_reports_tri_state_transitions():
    before = nextcord.PermissionOverwrite(send_messages=True, add_reactions=False)
    after = nextcord.PermissionOverwrite(send_messages=None, add_reactions=True)

    lines = diff_overwrite(before, after)

    assert any("Send Messages" in line and "➖ Inherit" in line for line in lines)
    assert any("Add Reactions" in line and "✅ Allow" in line for line in lines)


def test_overwrite_map_is_keyed_by_target_id():
    role = make_role(2, "Helper")
    channel = make_channel(overwrites={role: nextcord.PermissionOverwrite()})

    assert list(overwrite_map(channel)) == [2]


# ----------------------------------------------------------------------
# Emoji events
# ----------------------------------------------------------------------


def make_emoji(emoji_id, name, animated=False):
    return SimpleNamespace(
        id=emoji_id,
        name=name,
        animated=animated,
        url=f"https://cdn.discordapp.com/emojis/{emoji_id}.png",
    )


def test_emoji_create_and_delete_are_logged():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    old = make_emoji(1, "wave")
    new = make_emoji(2, "party")

    asyncio.run(EmojiLog(fake_bot(channel=channel)).on_guild_emojis_update(guild, [old], [new]))

    titles = [embed.title for embed in sent_embeds(channel)]
    assert titles == ["Emoji Created", "Emoji Deleted"]


def test_emoji_rename_is_logged():
    channel = log_channel()
    guild = fake_guild(channels=[channel])

    asyncio.run(
        EmojiLog(fake_bot(channel=channel)).on_guild_emojis_update(
            guild, [make_emoji(1, "wave")], [make_emoji(1, "hello")]
        )
    )

    embed = only_embed(channel)
    assert embed.title == "Emoji Renamed"
    assert field_value(embed, "Before") == "`:wave:`"
    assert field_value(embed, "After") == "`:hello:`"


def test_unchanged_emoji_list_is_silent():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    emojis = [make_emoji(1, "wave")]

    asyncio.run(EmojiLog(fake_bot(channel=channel)).on_guild_emojis_update(guild, emojis, emojis))

    channel.send.assert_not_awaited()


# ----------------------------------------------------------------------
# Invite events
# ----------------------------------------------------------------------


def make_message(content, guild, author=None, channel_id=200):
    return SimpleNamespace(
        id=999,
        content=content,
        guild=guild,
        author=author or make_member(guild=guild),
        channel=SimpleNamespace(id=channel_id, mention=f"<#{channel_id}>"),
        jump_url="https://discord.com/channels/1/2/3",
    )


@pytest.mark.parametrize(
    "content,expected",
    [
        ("join https://discord.gg/abc123", ["abc123"]),
        ("discord.com/invite/xyz", ["xyz"]),
        ("http://discordapp.com/invite/Legacy1", ["Legacy1"]),
        ("discord.gg/one and discord.gg/one", ["one"]),
        ("no invites here", []),
        ("discordxgg/abc", []),
    ],
)
def test_invite_code_detection(content, expected):
    cog = InviteLog(fake_bot())
    assert cog.find_invite_codes(content) == expected


def test_invite_log_includes_resolved_server_details():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    bot = fake_bot(channel=channel)
    bot.fetch_invite = AsyncMock(
        return_value=SimpleNamespace(
            guild=SimpleNamespace(id=OTHER_GUILD_ID, name="Other Server", icon=None),
            channel=SimpleNamespace(name="welcome"),
            inviter=make_member(member_id=42, name="inviter"),
            approximate_member_count=1234,
            approximate_presence_count=56,
            expires_at=None,
        )
    )

    asyncio.run(InviteLog(bot).on_message(make_message("come to discord.gg/abc", guild)))

    embed = only_embed(channel)
    assert embed.title == "Invite Posted"
    assert "Other Server" in field_value(embed, "Invite Target")
    assert field_value(embed, "Server Size") == "`1234` members • `56` online"
    assert field_value(embed, "Expires") == "`Never`"


def test_invite_log_handles_unresolvable_invites():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    bot = fake_bot(channel=channel)
    bot.fetch_invite = AsyncMock(side_effect=RuntimeError("404"))

    asyncio.run(InviteLog(bot).on_message(make_message("discord.gg/dead", guild)))

    assert "Could not be resolved" in field_value(only_embed(channel), "Invite Target")


def test_invite_log_ignores_bots_and_ignored_channels():
    channel = log_channel()
    guild = fake_guild(channels=[channel])

    bot_message = make_message("discord.gg/abc", guild, author=make_member(bot=True))
    asyncio.run(InviteLog(fake_bot(channel=channel)).on_message(bot_message))

    ignored_bot = fake_bot(channel=channel, config={"server_log_ignored_channel_ids": [200]})
    asyncio.run(InviteLog(ignored_bot).on_message(make_message("discord.gg/abc", guild)))

    channel.send.assert_not_awaited()


# ----------------------------------------------------------------------
# Moderator command events
# ----------------------------------------------------------------------


def slash_interaction(data, guild, user=None, channel_id=200):
    return SimpleNamespace(
        data=data,
        guild=guild,
        user=user or make_member(member_id=9, name="mod", guild=guild),
        channel=SimpleNamespace(id=channel_id, mention=f"<#{channel_id}>"),
        application_command=SimpleNamespace(qualified_name=data.get("name")),
    )


def test_resolve_command_name_walks_subcommands():
    data = {
        "name": "bonk",
        "options": [{"name": "purge", "type": 1, "options": [{"name": "user", "type": 6, "value": "5"}]}],
    }

    assert resolve_command_name(SimpleNamespace(data=data)) == "bonk purge"
    assert leaf_options(SimpleNamespace(data=data)) == [{"name": "user", "type": 6, "value": "5"}]


def test_format_option_value_renders_mentions_and_booleans():
    assert format_option_value({"type": 6, "value": "5"}) == "<@5>"
    assert format_option_value({"type": 7, "value": "8"}) == "<#8>"
    assert format_option_value({"type": 8, "value": "9"}) == "<@&9>"
    assert format_option_value({"type": 5, "value": True}) == "`Yes`"
    assert format_option_value({"type": 3, "value": "spam"}) == "`spam`"


def test_mod_command_log_records_slash_usage():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    interaction = slash_interaction(
        {
            "name": "ban",
            "options": [
                {"name": "member", "type": 6, "value": "1"},
                {"name": "reason", "type": 3, "value": "raiding"},
            ],
        },
        guild,
    )

    asyncio.run(ModCommandLog(fake_bot(channel=channel)).on_application_command_completion(interaction))

    embed = only_embed(channel)
    assert embed.title == "Moderator Command Used"
    assert field_value(embed, "Command") == "`ban`"
    usage = field_value(embed, "Usage")
    assert "<@1>" in usage and "raiding" in usage


def test_mod_command_log_ignores_non_moderator_commands():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    interaction = slash_interaction({"name": "wordle"}, guild)

    asyncio.run(ModCommandLog(fake_bot(channel=channel)).on_application_command_completion(interaction))

    channel.send.assert_not_awaited()


def test_mod_command_list_is_configurable():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    bot = fake_bot(channel=channel, config={"server_log_mod_commands": ["wordle"]})
    interaction = slash_interaction({"name": "wordle"}, guild)

    asyncio.run(ModCommandLog(bot).on_application_command_completion(interaction))

    assert only_embed(channel).title == "Moderator Command Used"


def test_mod_command_log_records_prefix_commands():
    channel = log_channel()
    guild = fake_guild(channels=[channel])
    ctx = SimpleNamespace(
        guild=guild,
        command=SimpleNamespace(qualified_name="warn", name="warn"),
        author=make_member(member_id=9, name="mod", guild=guild),
        channel=SimpleNamespace(id=200, mention="<#200>"),
        message=SimpleNamespace(content="ap:warn @user spamming"),
    )

    asyncio.run(ModCommandLog(fake_bot(channel=channel)).on_command_completion(ctx))

    assert field_value(only_embed(channel), "Usage") == "`ap:warn @user spamming`"


# ----------------------------------------------------------------------
# Truncation safety
# ----------------------------------------------------------------------


def test_clip_respects_embed_field_limit():
    clipped = base.clip("x" * 5000, base.FIELD_LIMIT)

    assert len(clipped) <= base.FIELD_LIMIT
    assert clipped.endswith("*(cut off)*")


def test_channel_update_caps_permission_fields():
    channel = log_channel()
    guild = fake_guild(channels=[channel])

    before = make_channel(overwrites={})
    after = make_channel(
        overwrites={
            make_role(index, f"Role {index}"): nextcord.PermissionOverwrite(send_messages=True)
            for index in range(2, 22)
        }
    )
    before.guild = after.guild = guild

    asyncio.run(ChannelLog(fake_bot(channel=channel)).on_guild_channel_update(before, after))

    embed = only_embed(channel)
    assert len(embed.fields) <= 25
    assert field_value(embed, "Note") == "+12 more permission target(s) changed."
