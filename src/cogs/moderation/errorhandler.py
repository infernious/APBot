import nextcord
from nextcord import Interaction
from nextcord.ext import commands


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_load(self):
        print("[ErrorHandler] Loaded.")
        self.bot.tree.on_error = self.on_app_command_error

    def cog_unload(self):
        self.bot.tree.on_error = None  # clear custom handler

    async def on_app_command_error(self, interaction: Interaction, error: Exception):
        embed = nextcord.Embed(title="❌ Slash Command Error", color=nextcord.Color.red())

        if isinstance(error, commands.CheckFailure):
            embed.add_field(name="Check Failure", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.NoPrivateMessage):
            embed.add_field(name="No Private Message", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.MissingRole):
            embed.add_field(name="Missing Role", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.MissingAnyRole):
            embed.add_field(name="Missing Any Role", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.MissingPermissions):
            embed.add_field(name="Missing Permissions", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.BotMissingPermissions):
            embed.add_field(name="Bot Missing Permissions", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.CommandOnCooldown):
            embed.add_field(name="Command On Cooldown", value=f"```\n{error}\n```", inline=False)
        elif isinstance(error, commands.CommandNotFound):
            embed.add_field(name="Command Not Found", value=f"```\n{error}\n```", inline=False)
        else:
            embed.add_field(name="Unhandled Error", value="Something went wrong.")
            embed.add_field(name="Details", value=f"```\n{error}\n```", inline=False)

        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except nextcord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(ErrorHandler(bot))
