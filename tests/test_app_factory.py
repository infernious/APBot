from app_factory import build_bot, build_default_colors


class FakeConf:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


class DummyBot:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def event(self, callback):
        self.on_ready = callback
        return callback


def test_build_default_colors_merges_configured_colors():
    conf = FakeConf({"colors": {"red": "0x123456", "green": 255}})

    colors = build_default_colors(conf)

    assert colors["red"] == 0x123456
    assert colors["green"] == 255
    assert colors["yellow"] == 0xFFFF00


def test_build_bot_attaches_config_db_and_colors(monkeypatch):
    conf = FakeConf({"command_prefix": "??", "colors": {"blue": "0x111111"}})
    fake_db = object()

    monkeypatch.setattr("app_factory.APBot", DummyBot)
    monkeypatch.setattr("app_factory.Database", lambda config: fake_db)

    bot = build_bot(conf)

    assert bot.kwargs["command_prefix"] == "??"
    assert bot.kwargs["strip_after_prefix"] is True
    assert bot.config is conf
    assert bot.db is fake_db
    assert bot.colors["blue"] == 0x111111
    assert hasattr(bot, "on_ready")
