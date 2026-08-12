import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cogs.pfp_log import PFP_LOGS_CHANNEL_ID, PfpLogCog
from startup import DEFAULT_COGS


LOGS_CHANNEL_ID = 5000
GUILD_ID = 777


def asset(url):
    return SimpleNamespace(url=url)


def build_bot(channel=None, member_in_guild=True, config=None):
    logs_channel = channel if channel is not None else SimpleNamespace(send=AsyncMock())
    guild = SimpleNamespace(get_member=lambda user_id: SimpleNamespace(id=user_id) if member_in_guild else None)

    return SimpleNamespace(
        config=SimpleNamespace(
            get=(config or {"pfp_logs_channel": LOGS_CHANNEL_ID, "guild_id": GUILD_ID}).get
        ),
        get_channel=lambda channel_id: logs_channel if channel_id == LOGS_CHANNEL_ID else None,
        get_guild=lambda guild_id: guild if guild_id == GUILD_ID else None,
    ), logs_channel


def user(user_id=1, name="pushi", avatar_url="https://cdn.discordapp.com/avatars/1/old.png", bot=False, avatar=True):
    return SimpleNamespace(
        id=user_id,
        name=name,
        display_name=name,
        mention=f"<@{user_id}>",
        bot=bot,
        avatar=asset(avatar_url) if avatar else None,
        display_avatar=asset(avatar_url),
    )


def member(user_id=1, name="pushi", avatar_url="https://cdn.discordapp.com/avatars/1/old.png", guild_avatar_url=None, bot=False, avatar=True):
    base = user(user_id=user_id, name=name, avatar_url=avatar_url, bot=bot, avatar=avatar)
    base.guild_avatar = asset(guild_avatar_url) if guild_avatar_url else None
    base.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return base


def sent_embed(channel):
    channel.send.assert_awaited_once()
    return channel.send.await_args.kwargs["embed"]


def test_pfp_log_is_loaded_by_default():
    assert "cogs.pfp_log" in DEFAULT_COGS


def test_join_logs_current_profile_picture():
    bot, channel = build_bot()
    cog = PfpLogCog(bot)
    joiner = member(avatar_url="https://cdn.discordapp.com/avatars/1/join.png")

    asyncio.run(cog.on_member_join(joiner))

    embed = sent_embed(channel)
    assert "joined with this profile picture" in embed.description
    assert embed.image.url == "https://cdn.discordapp.com/avatars/1/join.png"
    assert embed.footer.text.startswith("User ID: 1")


def test_join_notes_default_avatar():
    bot, channel = build_bot()
    cog = PfpLogCog(bot)
    joiner = member(avatar_url="https://cdn.discordapp.com/embed/avatars/0.png", avatar=False)

    asyncio.run(cog.on_member_join(joiner))

    embed = sent_embed(channel)
    assert any(field.value == "Using the default Discord avatar" for field in embed.fields)


def test_join_ignores_bots():
    bot, channel = build_bot()
    cog = PfpLogCog(bot)

    asyncio.run(cog.on_member_join(member(bot=True)))

    channel.send.assert_not_awaited()


def test_avatar_change_logs_old_and_new():
    bot, channel = build_bot()
    cog = PfpLogCog(bot)
    before = user(avatar_url="https://cdn.discordapp.com/avatars/1/old.png")
    after = user(avatar_url="https://cdn.discordapp.com/avatars/1/new.png")

    asyncio.run(cog.on_user_update(before, after))

    embed = sent_embed(channel)
    assert "changed their profile picture" in embed.description
    assert embed.thumbnail.url == "https://cdn.discordapp.com/avatars/1/old.png"
    assert embed.image.url == "https://cdn.discordapp.com/avatars/1/new.png"


def test_username_only_change_is_ignored():
    bot, channel = build_bot()
    cog = PfpLogCog(bot)
    before = user(name="pushi")
    after = user(name="pushiscool")

    asyncio.run(cog.on_user_update(before, after))

    channel.send.assert_not_awaited()


def test_avatar_change_ignores_users_outside_the_guild():
    bot, channel = build_bot(member_in_guild=False)
    cog = PfpLogCog(bot)
    before = user(avatar_url="https://cdn.discordapp.com/avatars/1/old.png")
    after = user(avatar_url="https://cdn.discordapp.com/avatars/1/new.png")

    asyncio.run(cog.on_user_update(before, after))

    channel.send.assert_not_awaited()


def test_server_avatar_change_is_logged():
    bot, channel = build_bot()
    cog = PfpLogCog(bot)
    before = member(guild_avatar_url=None)
    after = member(guild_avatar_url="https://cdn.discordapp.com/guilds/2/users/1/server.png")

    asyncio.run(cog.on_member_update(before, after))

    embed = sent_embed(channel)
    assert "changed their server profile picture" in embed.description
    assert embed.image.url == "https://cdn.discordapp.com/guilds/2/users/1/server.png"


def test_server_avatar_removal_is_logged():
    bot, channel = build_bot()
    cog = PfpLogCog(bot)
    before = member(guild_avatar_url="https://cdn.discordapp.com/guilds/2/users/1/server.png")
    after = member(guild_avatar_url=None)

    asyncio.run(cog.on_member_update(before, after))

    embed = sent_embed(channel)
    assert "removed their server profile picture" in embed.description


def test_role_only_member_update_is_ignored():
    bot, channel = build_bot()
    cog = PfpLogCog(bot)

    asyncio.run(cog.on_member_update(member(), member()))

    channel.send.assert_not_awaited()


def test_nothing_is_logged_without_a_configured_channel():
    bot, channel = build_bot(config={"guild_id": GUILD_ID})
    cog = PfpLogCog(bot)

    asyncio.run(cog.on_member_join(member()))

    channel.send.assert_not_awaited()


def test_missing_config_key_falls_back_to_default_channel():
    logs_channel = SimpleNamespace(send=AsyncMock())
    bot = SimpleNamespace(
        config=SimpleNamespace(get=lambda key, default=None: {"guild_id": GUILD_ID}.get(key, default)),
        get_channel=lambda channel_id: logs_channel if channel_id == PFP_LOGS_CHANNEL_ID else None,
        get_guild=lambda guild_id: None,
    )
    cog = PfpLogCog(bot)

    asyncio.run(cog.on_member_join(member()))

    logs_channel.send.assert_awaited_once()
