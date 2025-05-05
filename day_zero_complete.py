from discord.ext import commands
from discord import app_commands
import discord

nonessential_textchannels = ["welcome", "general-2", "college", "bot-commands",
                             "post-ap-math", "higher-cs", "higher-other",
                             "aphome-econ", "apresearch", "apart-design"]

class DayZeroComplete(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("✅ DayZeroComplete cog initialized.")
        self.bot.tree.add_command(self.dayzero_group)

    dayzero_group = app_commands.Group(
        name="dayzero",
        description="Manage non-essential channels for day zero lock.",
        guild_only=True,
        default_permissions=discord.Permissions(administrator=True)
    )

    @dayzero_group.command(name="close_nonessential", description="Close non-essential channels to members.")
    async def close_nonessential(self, interaction: discord.Interaction):
        print("⛔ close_nonessential command triggered.")
        guild = interaction.guild
        staff_role = discord.utils.get(guild.roles, name="staff")
        categories_to_close = ["Events", "Lounge", "Voice Channels"]

        for ch_name in nonessential_textchannels:
            channel = discord.utils.get(guild.text_channels, name=ch_name)
            if channel:
                await channel.set_permissions(guild.default_role, view_channel=False, send_messages=False)
                await channel.set_permissions(staff_role, view_channel=True, send_messages=True)

        for category_name in categories_to_close:
            category = discord.utils.get(guild.categories, name=category_name)
            if category:
                for channel in category.channels:
                    perms = {"view_channel": False}
                    if isinstance(channel, discord.VoiceChannel):
                        perms["connect"] = False
                    await channel.set_permissions(guild.default_role, **perms)
                    await channel.set_permissions(staff_role, view_channel=True, connect=True)

        await interaction.response.send_message("✅ Non-essential channels have been closed.", ephemeral=True)

    @dayzero_group.command(name="open_nonessential", description="Reopen non-essential channels to members.")
    async def open_nonessential(self, interaction: discord.Interaction):
        print("🔓 open_nonessential command triggered.")
        guild = interaction.guild
        staff_role = discord.utils.get(guild.roles, name="staff")
        categories_to_open = ["Events", "Lounge", "Voice Channels"]

        for ch_name in nonessential_textchannels:
            channel = discord.utils.get(guild.text_channels, name=ch_name)
            if channel:
                await channel.set_permissions(guild.default_role, view_channel=True, send_messages=True)
                await channel.set_permissions(staff_role, overwrite=None)

        for category_name in categories_to_open:
            category = discord.utils.get(guild.categories, name=category_name)
            if category:
                for channel in category.channels:
                    perms = {"view_channel": True}
                    if isinstance(channel, discord.VoiceChannel):
                        perms["connect"] = True
                    await channel.set_permissions(guild.default_role, **perms)
                    await channel.set_permissions(staff_role, overwrite=None)

        await interaction.response.send_message("✅ Non-essential channels have been reopened.", ephemeral=True)


async def setup(bot: commands.Bot):
    print("✅ Loading DayZeroComplete cog.")
    await bot.add_cog(DayZeroComplete(bot))
    print("✅ Loaded: DayZeroComplete")
