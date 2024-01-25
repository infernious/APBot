from typing import Union

import orjson


class Config:
    def __init__(self, fn: str) -> None:
        self.fn = fn
        self.refresh()

    def refresh(self):
        with open(self.fn) as f:
            self.config: dict = orjson.loads(f.read())

    def update(self, key: Union[dict, str], value: Union[dict, str, int, list]) -> None:
        self.config[key] = value
        with open(self.fn, "w") as f:
            f.write(orjson.dumps(self.config, option=orjson.OPT_INDENT_2).decode())

    def get(self, key: Union[str, dict], default=None) -> Union[dict, str, int, list]:
        self.refresh()
        return self.config.get(key, default)
