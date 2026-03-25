import os
from dotenv import load_dotenv
from app_config import load_required_config
from app_factory import build_bot
from startup import startup


def main(config_path: str | None = None) -> None:
    load_dotenv()
    print("Current working directory:", os.getcwd())

    conf = load_required_config(config_path)
    bot = build_bot(conf)
    bot.loop.create_task(startup(bot, conf))
    bot.run(os.getenv("APBOT_BOT_TOKEN"))


if __name__ == "__main__":
    main()
