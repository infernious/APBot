from app_config import EmptyConfig, get_command_guild_ids, load_optional_config, load_required_config


def test_load_required_config_reads_explicit_path(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"guild_id":123,"command_prefix":"ap:"}', encoding="utf-8")

    conf = load_required_config(str(config_path))

    assert conf.get("guild_id") == 123
    assert conf.get("command_prefix") == "ap:"


def test_load_optional_config_returns_empty_config_for_missing_file(tmp_path):
    conf = load_optional_config(str(tmp_path / "missing.json"))

    assert conf.get("guild_id") is None
    assert conf.get("fallback", "default") == "default"


def test_get_command_guild_ids_returns_expected_shape():
    assert get_command_guild_ids(EmptyConfig()) is None
    assert get_command_guild_ids(type("Conf", (), {"get": lambda self, key, default=None: 42 if key == "guild_id" else default})()) == [42]
