import discord
from discord import Interaction
from discord import app_commands
from discord.app_commands import AppCommandError
from discord.ext import commands


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_load(self):
        tree = self.bot.tree
        tree.on_error = self.on_app_command_error

    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = tree.__class__.on_error

    # the global error handler for all app commands (slash & ctx menus)
    async def on_app_command_error(self, interaction: Interaction, error: AppCommandError):

        error_message = discord.Embed(title="", color=0xff0000)

        if isinstance(error, app_commands.CheckFailure):
            error_message.add_field(name='Error: Check Failure', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.NoPrivateMessage):
            error_message.add_field(name='Error: No Private Message', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.MissingRole):
            error_message.add_field(name='Error: Missing Role', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.MissingAnyRole):
            error_message.add_field(name='Error: Missing Any Role', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.MissingPermissions):
            error_message.add_field(name='Error: Missing Permissions', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.BotMissingPermissions):
            error_message.add_field(name='Error: Bot Missing Permissions', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.CommandOnCooldown):
            error_message.add_field(name='Error: Command On Cooldown', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.CommandLimitReached):
            error_message.add_field(name='Error: Command Limit Reached', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.CommandAlreadyRegistered):
            error_message.add_field(name='Error: Command Already Registered', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.CommandSignatureMismatch):
            error_message.add_field(name='Error: Command Signature Mismatch', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.CommandNotFound):
            error_message.add_field(name='Error: Command Not Found', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.MissingApplicationID):
            error_message.add_field(name='Error: Missing Application ID', value=f'```\n{error}\n```', inline=False)
        elif isinstance(error, app_commands.CommandSyncFailure):
            error_message.add_field(name='Error: Command Sync Failure', value=f'```\n{error}\n```', inline=False)
        else:
            error_message.add_field(name='Error!',
                                    value=f'Something went wrong with the command. '
                                          f'Please double check your input and try again.')
            error_message.add_field(name='Error Message:', value=f'```\n{error}\n```', inline=False)

        try:
            await interaction.response.send_message(embed=error_message, ephemeral=True)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(embed=error_message, ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(ErrorHandler(bot), guilds=[discord.Object(id=bot.guild_id)])
