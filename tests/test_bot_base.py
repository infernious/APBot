import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bot_base import APBot


def make_bot():
    return object.__new__(APBot)


def test_getch_guild_prefers_cache():
    bot = make_bot()
    guild = object()
    bot.get_guild = Mock(return_value=guild)
    bot.fetch_guild = AsyncMock()

    result = asyncio.run(APBot.getch_guild(bot, 123))

    assert result is guild
    bot.fetch_guild.assert_not_awaited()


def test_getch_user_falls_back_to_fetch():
    bot = make_bot()
    user = object()
    bot.get_user = Mock(return_value=None)
    bot.fetch_user = AsyncMock(return_value=user)

    result = asyncio.run(APBot.getch_user(bot, 456))

    assert result is user
    bot.fetch_user.assert_awaited_once_with(456)


def test_getch_member_returns_false_when_guild_lookup_fails():
    bot = make_bot()
    bot.getch_guild = AsyncMock(return_value=False)

    result = asyncio.run(APBot.getch_member(bot, 1, 2))

    assert result is False


def test_getch_channel_returns_false_when_fetch_raises():
    bot = make_bot()
    bot.get_channel = Mock(return_value=None)
    bot.fetch_channel = AsyncMock(side_effect=RuntimeError("boom"))

    result = asyncio.run(APBot.getch_channel(bot, 789))

    assert result is False


def test_getch_message_fetches_message_from_channel():
    bot = make_bot()
    message = object()
    channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message))
    bot.getch_channel = AsyncMock(return_value=channel)

    result = asyncio.run(APBot.getch_message(bot, 111, 222))

    assert result is message
    channel.fetch_message.assert_awaited_once_with(222)
