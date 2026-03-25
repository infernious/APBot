import pytest

from config_handler import Config


@pytest.fixture(autouse=True)
def reset_config_print_flag():
    Config._printed = False


def test_config_loads_valid_json(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"command_prefix":"ap:","guild_id":123}', encoding="utf-8")

    config = Config(str(config_path))

    assert config.get("command_prefix") == "ap:"
    assert config.get("guild_id") == 123
    assert config.get("missing_key", "fallback") == "fallback"


def test_config_raises_for_missing_file(tmp_path):
    missing_path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError, match="Config file not found"):
        Config(str(missing_path))


def test_config_raises_for_empty_file(tmp_path):
    empty_path = tmp_path / "empty.json"
    empty_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Config file is empty"):
        Config(str(empty_path))


def test_config_raises_for_invalid_json(tmp_path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{bad json}", encoding="utf-8")

    with pytest.raises(ValueError, match="Failed to decode JSON"):
        Config(str(bad_path))
