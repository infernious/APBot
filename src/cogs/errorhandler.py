import nextcord
from nextcord import Interaction
from nextcord.ext import commands


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_load(self):
        self.bot.tree.on_error = self.on_app_command_error

    def cog_unload(self):
        self.bot.tree.on_error = self.bot.tree.__class__.on_error

    async def on_app_command_error(self, interaction: Interaction, error: Exception):
        # Create an error embed
        error_message = nextcord.Embed(title="An Error Occurred", color=0xff0000)

        if isinstance(error, commands.CheckFailure):
            error_message.add_field(name="Error: Check Failure", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.NoPrivateMessage):
            error_message.add_field(name="Error: No Private Message", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.MissingRole):
            error_message.add_field(name="Error: Missing Role", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.MissingAnyRole):
            error_message.add_field(name="Error: Missing Any Role", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.MissingPermissions):
            error_message.add_field(name="Error: Missing Permissions", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.BotMissingPermissions):
            error_message.add_field(name="Error: Bot Missing Permissions", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.CommandOnCooldown):
            error_message.add_field(name="Error: Command On Cooldown", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.CommandNotFound):
            error_message.add_field(name="Error: Command Not Found", value=f"```\n{error}\n```", inline=False)
        else:
            # Handle unexpected errors
            error_message.add_field(
                name="Unexpected Error",
                value="An unexpected error occurred. Please report this to the bot developer.",
                inline=False,
            )
            error_message.add_field(name="Details", value=f"```\n{error}\n```", inline=False)

        # Try to respond to the interaction, or use followup if already responded
        try:
            await interaction.response.send_message(embed=error_message, ephemeral=True)
        except nextcord.errors.InteractionResponded:
            await interaction.followup.send(embed=error_message, ephemeral=True)


async def setup(bot: commands.Bot):
    # Use dynamic guilds if needed, or pass an empty list for global cog registration
    await bot.add_cog(ErrorHandler(bot))
