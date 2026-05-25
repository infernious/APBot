# APBot v3.1 (beta)

This is the source code for the community and moderation bot for the AP Students Discord Server (https://discord.gg/apstudents).

## Development Setup

Follow the steps below to set up APBot locally.

1. Create your own bot
Create a Discord bot through the Discord Developer Portal and get your bot token.

2. Fork the repository
Fork this repository and clone it to your machine.

```bash
git clone https://github.com/infernious/APBot
cd APBot
```

3. Switch to the `ap-bot-3v` branch.

4. Create server(s)

If you are only using one server, open `main.py` and comment out:

```python
"cogs.moderation.appeal"
```

Otherwise, you may need to create two servers, one for the main bot and one for ban appeals.

5. Create a `.env` file

Add the following variables to your `.env` file:

```env
APBOT_BOT_TOKEN=YOUR_BOT_TOKEN
APBOT_DATABASE_CONNECT_URL=YOUR_MONGO_DB_URL
```

6. Change the database name

In `database_handler.py`, change:

```python
self.database = database_client["ap-students"]
```

to:

```python
self.database = database_client["ap-test"]
```

7. Create `config.json`

Create a file called `config.json` and include the following variables:

```json
{
  "application_id": ,
  "guild_id": ,
  "ban_appeal_server": ,
  "command_prefix": "ap:",
  "modmail_channel": ,
  "appeals_channel_id": ,
  "server_log_channel": ,
  "bot_logs_channel":
}
```

Descriptions:

- `application_id`: Your bot application ID
- `guild_id`: The server where the bot runs
- `ban_appeal_server`: Server used for ban appeals
- `modmail_channel`: ID of the `#modmail` channel
- `appeals_channel_id`: ID of the `#ban-appeals` channel
- `server_log_channel`: ID of the `#server-log` channel
- `bot_logs_channel`: ID of the `#bot-log` channel

If you are only using one server, you can ignore:

- `ban_appeal_server`
- `appeals_channel_id`

8. Run the bot

Run the bot with:

```bash
python main.py
```

**NOTE**: Make sure to run the following command prior to doing such:

`python3 -m pip install -r requirements.txt`

If everything is configured correctly, the bot should start successfully.

## Ways to Contribute

You can help APBot in several ways, including:
- Reporting bugs
- Adding new features
- Refactoring existing code
- Improving documentation such as this file or `README.md`

## More on Adding New Features

If you would like to add a new feature, please follow these steps:

1. Open an issue describing the feature you would like to implement.
2. Wait for feedback or approval from the maintainers.
3. Fork the repository and create a new branch (off of the `ap-bot-3v` branch) for your feature.
4. Install dependencies with `python3 -m pip install -r requirements.txt`.
5. Implement your changes locally.
6. Run `python3 -m pytest`, making sure the repo passes all test cases.
   - **Note:** These test cases can be found in the `/tests` folder.
   - Feel free to run individual test files as needed.
7. Submit a pull request into `ap-bot-3v` explaining what your feature does.
   - **Note:** GitHub Actions will run all test cases when you open your PR.

Please make sure that:
- Your code is clean and readable
- Your changes stay focused on the feature you are adding
- Your commit messages are understandable
- Your pull request includes a clear description of the change

## Reporting Bugs

If you find a bug, please open an issue and include:
- A clear description of the bug
- Steps to reproduce it
- The expected behavior
- Screenshots when helpful

## Code Style Guide

### 1. Project Structure

The codebase is organized around the Discord bot runtime:

- `src/main.py` is the entry point that builds the bot, loads config, defines shared colors, loads cogs, and starts the application.
- `src/bot_base.py` contains the custom `APBot` subclass and reusable Discord fetch helpers.
- `src/database_handler.py` contains database access classes and data-layer logic.
- `src/models.py` and `src/cogs/exams_automation/models.py` hold small domain models and helpers.
- `src/cogs/` contains feature modules, usually one cog per file.
- `src/cogs/moderation/` groups moderation-specific cogs into a dedicated package.
- `src/cogs/exams_automation/` groups a more specialized feature area with its own models and day-based workflows.

When adding new code:

- Put new Discord features in `src/cogs/`.
- Put moderation-specific features in `src/cogs/moderation/`.
- Put cross-cutting helpers in top-level modules only when they are used by more than one cog.
- Keep data access in `database_handler.py` or a closely related database abstraction, not embedded deep inside command handlers unless it is truly command-specific.

### 2. File and Module Naming

Observed convention:

- Python modules use `snake_case`.
- Cog filenames are descriptive and usually match the feature area, for example `modmail.py`, `study.py`, `tags.py`, `role_log.py`, and `voice_log.py`.
- Packages are used where a feature area is broad enough to deserve grouping, such as `cogs.moderation`.

Guidelines:

- Use `snake_case.py` for new files.
- Name files after the feature they own, not after vague implementation details.
- Prefer short, descriptive names like `appeal.py` or `errorhandler.py` over overloaded names like `helpers2.py`.
- If a feature grows into multiple related modules, create a package and group them under a shared namespace.
- Match the import path you intend to load from `main.py`. If a cog will be loaded as `cogs.feature_name`, keep the filename aligned with that name.

### 3. Class and Function Naming

- Classes use `PascalCase`.
- Cog classes are named after the feature, for example `Tags`, `Modmail`, `ModerationCommands`, and `RawReactionCog`.
- Functions and methods use `snake_case`.
- Command handlers are usually named after the slash command or subcommand they implement.

Guidelines:

- Use `PascalCase` for classes and `snake_case` for functions, methods, and variables.
- Name cog classes by behavior or domain, not by framework terms alone.
- Keep listener names aligned with Discord events when using `@commands.Cog.listener()`.
- Name helper methods clearly by intent, for example `_has_required_role`, `get_user_infractions`, or `convert_time`.
- If a function is internal-only, a leading underscore is preferred for helpers inside a module or class.

### 4. Cog Layout and Command Organization

The repository strongly favors class-based cogs with a predictable shape:

1. Imports
2. Config/bootstrap values
3. Constants
4. Cog class
5. Slash commands, listeners, and helper methods
6. `setup(bot)` registration function

Follow that layout for new cogs whenever practical.

Recommended cog structure:

```python
import nextcord
from nextcord.ext import commands

from bot_base import APBot
from config_handler import Config

config_path = "config.json"
conf = Config(config_path)


class Example(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    def _helper(self) -> bool:
        return True

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        print("Example cog ready.")


def setup(bot: APBot) -> None:
    bot.add_cog(Example(bot))
```

Additional expectations:

- Keep reusable helper logic near the cog that owns it unless it is broadly shared.
- Put permission checks near the top of command handlers.
- Keep slash command decorators compact and readable when possible.
- If a command has many options, one-per-line formatting is preferred.
- End each cog file with a single `setup(bot)` function.

### 5. Imports

- Standard-library imports usually appear first.
- Third-party imports like `nextcord`, `discord`, `motor`, and `dotenv` come next.
- Local imports such as `from bot_base import APBot` and `from config_handler import Config` come after that.
- Some files currently have duplicate or repeated imports. New contributions should avoid introducing more of that drift.

Guidelines:

- Group imports in this order: standard library, third-party, local project imports.
- Prefer one import block at the top of the file.
- Remove duplicate imports before opening a pull request.
- Prefer explicit imports when they improve readability, but avoid giant import lists if importing the module is clearer.
- If a file mixes `discord` and `nextcord`, keep usage intentional and document why if both are truly required.

### 6. Configuration Access

Load cofigs as such:

```python
config_path = "config.json"
conf = Config(config_path)
```

This is currently common across many cogs. Until the project centralizes config access further, contributors should stay compatible with that pattern.

Guidelines:

- Use the existing `Config` class for config file access.
- Keep config keys descriptive and consistent with existing names.
- Prefer `conf.get("key")` or `self.bot.config.get("key")` over hardcoding IDs directly in logic.
- For bot-wide shared configuration, prefer `self.bot.config` inside cogs once the bot instance is available.
- If you introduce new config values, document them in setup docs and examples.

### 7. Typing and Type Hints

- Type hints are used often, especially in helper methods and dataclasses.
- Some files use them more consistently than others.

Guidelines:

- Add type hints to new public functions, methods, and important internal helpers.
- Use the types already common in the repo, such as `Optional[...]`, `Union[...]`, and concrete Nextcord types like `Interaction`, `Member`, `TextChannel`, and `Embed`.
- Annotate `__init__` with `-> None`.
- Type annotate `setup(bot)` when practical.
- Prefer clear return types on utility functions and data-layer methods.
- If a return value can be absent, reflect that in the type instead of relying on comments alone.

### 8. Comments and Docstrings

- Helper methods in shared modules sometimes use short docstrings.
- Inline comments are common around Discord edge cases, permissions, cooldown logic, and compatibility handling.
- Larger files occasionally use section-divider comments to break up long flows.
- Some files contain commented-out code or temporary notes for future work.

Guidelines:

- Use docstrings for shared helpers, model methods, database methods, and non-obvious utilities.
- Keep docstrings short and practical. A one-line summary is usually enough unless behavior is subtle.
- Use inline comments to explain why something is done, especially for Discord API behavior, permissions, time conversions, cache-versus-fetch logic, or data migration compatibility.
- Do not add comments for obvious code. Prefer readable names first.
- Avoid leaving large blocks of commented-out code in new contributions. Open an issue or remove the dead code instead.
- If a file is long and split into major sections, section comments are acceptable, but keep them clean and sparse.

Good examples of comments for this project:

- Why a permission check must happen before a deferred interaction
- Why a timestamp is forced to UTC before storing
- Why a fallback fetch is needed when cache lookup fails
- Why a message should be ephemeral or visible to the full channel

### 9. Logging, Printing, and Error Handling

- The project currently uses a mix of `print(...)`, logger usage, and broad `try/except` blocks.
- Operational bot code often favors resilience over strict failure.

Guidelines:

- Follow the local pattern in the file you are editing, but prefer clearer error handling when adding new code.
- Use `print(...)` only for simple operational status messages if that is the surrounding file’s convention.
- Prefer `logging` for reusable modules or when a message represents an actual warning or error condition.
- Avoid bare `except:` in new code unless there is a strong reason. Catch the narrowest practical exception type.
- When swallowing an exception to keep the bot running, leave a short comment or log entry explaining the tradeoff.

### 10. Constants and Magic Values

- Role name sets and repeated IDs are often stored in module-level constants.
- Color maps and time conversion tables are defined once and reused.

Guidelines:

- Promote repeated literal values into named constants.
- Use uppercase names for true constants like `REQUIRED_ROLES`.
- Keep role-name allowlists and color maps near the top of the file.
- If a value belongs in config rather than source code, prefer config.

### 11. Async and Discord-Specific Patterns

This repository is mostly asynchronous and event-driven.

Guidelines:

- Keep Discord API operations `async` and await them directly.
- Defer interactions early when a command may take noticeable time.
- Put permission checks, channel checks, and guard clauses near the start of the command.
- Reuse `self.bot` helpers when the custom bot class already provides a cache-or-fetch path.
- Prefer small helper methods when a command starts mixing response formatting, permission handling, and database logic in one place.

### 12. Database and Model Code

Observed convention:

- Database access is centralized in database classes.
- Small data shapes are represented with dataclasses or structured dictionaries.
- Compatibility cleanup is sometimes handled at read time.

Guidelines:

- Keep persistence rules in database-layer code where possible.
- Normalize data as close to the read/write boundary as practical.
- When adding new stored fields, provide reasonable defaults for old records when needed.
- Keep model classes small and focused on data shape, not unrelated business logic.
- Document migration or backward-compatibility assumptions with a short comment when necessary.

### 13. Formatting and Readability

Based on the current repository, contributors should optimize first for readability and consistency with nearby code.

Guidelines:

- Prefer clear vertical spacing between logical sections.
- Use one blank line between top-level constants and class definitions.
- Keep long decorators and embed constructors readable by splitting arguments across lines.
- Favor descriptive variable names over abbreviations unless the abbreviation is already standard in the file.
- Avoid overly clever one-liners in command and listener code.
- If a function is becoming too long, split out helpers instead of stacking more inline comments.

### 14. Pull Request Expectations for Style

Before submitting a pull request:

- Match the naming and structure of the surrounding module.
- Remove unused imports and obviously dead code.
- Add type hints and short docstrings where they improve clarity.
- Check that new files are placed in the correct package.
- Keep comments focused on intent, API quirks, or edge cases.
- Avoid introducing a brand-new architectural pattern in a single file unless the maintainers have agreed to it first.xw

### 15. What "Consistent With APBot" Means

In practice, code that fits this project should look like this:

- Feature-oriented files
- Cog-based command organization
- Snake_case modules and functions
- PascalCase classes
- Config values read through `Config` or `self.bot.config`
- Short, practical comments instead of heavy documentation
- Type hints on important functions and helpers
- Readable async command handlers with early guard clauses

The current codebase is evolving, so consistency matters more than perfection. If you improve style while touching a file, keep those improvements scoped and respectful of the existing design.
