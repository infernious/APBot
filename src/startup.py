from typing import Optional, Sequence


DEFAULT_COGS = [
    "cogs.logs",
    "cogs.moderation.commands",
    "cogs.moderation.infraction",
    "cogs.bonk",
    "cogs.recurrent",
    "cogs.tags",
    "cogs.wordle",
    "cogs.scam_image_detector",
    "cogs.study",
    "cogs.helper_dm",
    "cogs.events",
    "cogs.modmail",
    "cogs.special",
    "cogs.moderation.appeal",
    "cogs.moderation.errorhandler",
    "cogs.moderation.decay",
    "cogs.rolereact",
    "cogs.boostrolemanager",
    "cogs.role_log",
    "cogs.voice_log",
    "cogs.pfp_log",
   # "cogs.exams_automation.day_zero_complete",
    "cogs.delete_log",
   # "cogs.leak_log",
    "cogs.media_leveling",
]


async def startup(bot, conf, extensions: Optional[Sequence[str]] = None) -> None:
    bot.rolemenu_view_set = False

    for extension in extensions or DEFAULT_COGS:
        try:
            bot.load_extension(extension)
            print(f"Successfully loaded extension {extension}")
        except Exception as e:
            print(f"Failed to load extension {extension}\n{type(e).__name__}: {e}")

    await bot.wait_until_ready()

    try:
        bot.guild = await bot.fetch_guild(conf.get("guild_id"))
        print(f"Fetched guild {bot.guild.name}")
    except Exception as e:
        print(f"Failed to fetch guild\n{type(e).__name__}: {e}")

    if getattr(bot, "user", None) is not None:
        bot.db.bot_user_id = bot.user.id

    try:
        guild_id = conf.get("guild_id")
        await bot.sync_application_commands(guild_id=guild_id)
        print(f"Guild commands synced to {guild_id}")
    except Exception as e:
        print(f"Failed to sync commands\n{type(e).__name__}: {e}")

    bot.owner_ids = conf.get("owner_ids", [])
    print("All Ready")
