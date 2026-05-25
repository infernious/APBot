import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from startup import DEFAULT_COGS, startup


def test_default_cogs_load_server_log_instead_of_delete_log():
    assert "cogs.server_log" in DEFAULT_COGS
    assert "cogs.delete_log" not in DEFAULT_COGS


class FakeConf:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_startup_loads_extensions_and_syncs_commands():
    conf = FakeConf({"guild_id": 123, "owner_ids": [1, 2]})
    bot = SimpleNamespace(
        rolemenu_view_set=True,
        load_extension=Mock(),
        wait_until_ready=AsyncMock(),
        fetch_guild=AsyncMock(return_value=SimpleNamespace(name="AP Students")),
        sync_application_commands=AsyncMock(),
        user=SimpleNamespace(id=999),
        db=SimpleNamespace(bot_user_id=None),
    )

    asyncio.run(startup(bot, conf, extensions=["cogs.one", "cogs.two"]))

    assert bot.rolemenu_view_set is False
    assert bot.load_extension.call_args_list[0].args == ("cogs.one",)
    assert bot.load_extension.call_args_list[1].args == ("cogs.two",)
    assert bot.guild.name == "AP Students"
    assert bot.db.bot_user_id == 999
    assert bot.owner_ids == [1, 2]
    bot.sync_application_commands.assert_awaited_once_with(guild_id=123)


def test_startup_continues_when_extension_or_sync_steps_fail():
    conf = FakeConf({"guild_id": 123, "owner_ids": []})

    def load_extension(name):
        if name == "broken":
            raise RuntimeError("bad extension")

    bot = SimpleNamespace(
        rolemenu_view_set=True,
        load_extension=Mock(side_effect=load_extension),
        wait_until_ready=AsyncMock(),
        fetch_guild=AsyncMock(side_effect=RuntimeError("no guild")),
        sync_application_commands=AsyncMock(side_effect=RuntimeError("no sync")),
        user=SimpleNamespace(id=999),
        db=SimpleNamespace(bot_user_id=None),
    )

    asyncio.run(startup(bot, conf, extensions=["good", "broken"]))

    assert bot.rolemenu_view_set is False
    assert bot.db.bot_user_id == 999
    assert bot.owner_ids == []
