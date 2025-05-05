from discord.ext import commands
from discord import app_commands
import discord

class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sync", description="Force sync slash commands to this guild.")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync_commands(self, interaction: discord.Interaction):
        await self.bot.tree.sync(guild=discord.Object(id=interaction.guild.id))
        await interaction.response.send_message("✅ Commands have been synced.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
