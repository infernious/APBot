from unittest.mock import Mock

import main


class FakeLoop:
    def __init__(self):
        self.scheduled = None

    def create_task(self, coro):
        self.scheduled = coro
        return coro


class FakeBot:
    def __init__(self):
        self.loop = FakeLoop()
        self.run = Mock()


def test_main_builds_bot_schedules_startup_and_runs(monkeypatch):
    conf = object()
    bot = FakeBot()

    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "load_required_config", lambda config_path=None: conf)
    monkeypatch.setattr(main, "build_bot", lambda loaded_conf: bot)

    async def fake_startup(bot_obj, conf_obj):
        return None

    monkeypatch.setattr(main, "startup", fake_startup)
    monkeypatch.setenv("APBOT_BOT_TOKEN", "test-token")

    main.main("custom-config.json")

    assert bot.loop.scheduled is not None
    assert bot.run.call_args.args == ("test-token",)
    bot.loop.scheduled.close()
