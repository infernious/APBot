import orjson

class Config:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.config = {}
        self.refresh()

    def refresh(self):
        try:
            with open(self.file_path, "r", encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    raise ValueError("Config file is empty")
                print(f"Config file contents: {content}")  # Debug print
                self.config = orjson.loads(content)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {self.file_path}")
        except orjson.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON from {self.file_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred while reading the config file: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)
