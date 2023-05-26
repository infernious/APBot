from discord import Embed, Interaction, Object, app_commands
from discord.app_commands import AppCommandError
from discord.errors import InteractionResponded
from discord.ext import commands

from bot_base import APBot


class ErrorHandler(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot

    def cog_load(self):
        tree = self.bot.tree
        tree.on_error = self.on_app_command_error

    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = tree.__class__.on_error

    # the global error handler for all app commands (slash & ctx menus)
    async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):
        error_message = Embed(title="", color=self.bot.colors["red"])
        formatted_error = f"```\n{error}\n```"

        if isinstance(error, app_commands.CheckFailure):
            error_message.add_field(name="Error: Check Failure", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.NoPrivateMessage):
            error_message.add_field(name="Error: No Private Message", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.MissingRole):
            error_message.add_field(name="Error: Missing Role", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.MissingAnyRole):
            error_message.add_field(name="Error: Missing Any Role", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.MissingPermissions):
            error_message.add_field(name="Error: Missing Permissions", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.BotMissingPermissions):
            error_message.add_field(name="Error: Bot Missing Permissions", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.CommandOnCooldown):
            error_message.add_field(name="Error: Command On Cooldown", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.CommandLimitReached):
            error_message.add_field(name="Error: Command Limit Reached", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.CommandAlreadyRegistered):
            error_message.add_field(name="Error: Command Already Registered", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.CommandSignatureMismatch):
            error_message.add_field(name="Error: Command Signature Mismatch", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.CommandNotFound):
            error_message.add_field(name="Error: Command Not Found", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.MissingApplicationID):
            error_message.add_field(name="Error: Missing Application ID", value=formatted_error, inline=False)
        elif isinstance(error, app_commands.CommandSyncFailure):
            error_message.add_field(name="Error: Command Sync Failure", value=formatted_error, inline=False)
        else:
            error_message.add_field(
                name="Error!", value="Something went wrong with the command. Please double check your input and try again."
            )
            error_message.add_field(name="Error Message:", value=formatted_error, inline=False)

        try:
            await interaction.response.send_message(embed=error_message, ephemeral=True)
        except InteractionResponded:
            await interaction.followup.send(embed=error_message, ephemeral=True)


async def setup(bot: APBot) -> None:
    await bot.add_cog(ErrorHandler(bot), guilds=[Object(id=bot.guild_id)])
