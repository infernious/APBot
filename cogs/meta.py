import discord
from discord import app_commands
from discord.ext import tasks, commands


class Meta(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.checks.has_role("Bot Staff")
    @app_commands.command()
    async def unload(self, interaction: discord.Interaction, cog: str):
        await self.bot.unload_extension(f"cogs.{cog}")
        await interaction.response.send_message(f'`cogs.{cog} unloaded`')

    @app_commands.checks.has_role("Bot Staff")
    @app_commands.command()
    async def load(self, interaction: discord.Interaction, cog: str):
        await self.bot.load_extension(f"cogs.{cog}")
        await interaction.response.send_message(f'`cogs.{cog} loaded`')

    @app_commands.checks.has_role("Bot Staff")
    @app_commands.command()
    async def reload(self, interaction: discord.Interaction, cog: str):
        await self.bot.unload_extension(f"cogs.{cog}")
        await self.bot.load_extension(f"cogs.{cog}")
        await interaction.response.send_message(f'`cogs.{cog} reloaded`')

    @app_commands.checks.has_role("Bot Staff")
    @app_commands.command()
    async def sync(self, interaction: discord.Interaction):
        await self.bot.tree.sync()
        await interaction.response.send_message("`Command tree synced.`")

async def setup(bot):
    await bot.add_cog(Meta(bot), guilds=[discord.Object(id=bot.guild_id)])
