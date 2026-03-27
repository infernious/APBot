import os
from pathlib import Path
from typing import Optional

from config_handler import Config


CONFIG_FILENAME = "config.json"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().with_name(CONFIG_FILENAME)


class EmptyConfig:
    def get(self, key, default=None):
        return default


def resolve_config_path(path: Optional[str] = None) -> Path:
    if path:
        return Path(path)

    env_path = os.getenv("APBOT_CONFIG_PATH")
    if env_path:
        return Path(env_path)

    cwd_path = Path(CONFIG_FILENAME)
    if cwd_path.exists():
        return cwd_path

    return DEFAULT_CONFIG_PATH


def load_required_config(path: Optional[str] = None) -> Config:
    config_path = resolve_config_path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if config_path.stat().st_size == 0:
        raise ValueError(f"Config file is empty: {config_path}")
    return Config(str(config_path))


def load_optional_config(path: Optional[str] = None):
    try:
        return load_required_config(path)
    except (FileNotFoundError, ValueError, RuntimeError):
        return EmptyConfig()


def get_command_guild_ids(conf=None):
    config = conf or load_optional_config()
    guild_id = config.get("guild_id")
    if guild_id is None:
        return None
    return [guild_id]
