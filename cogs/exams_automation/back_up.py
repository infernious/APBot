from discord.ext import commands
from discord import app_commands
import discord
import json
from datetime import datetime, timedelta


# Load config
with open('config.json') as f:
    config = json.load(f)

nonessential_textchannels = [
    "welcome", "general-2", "college", "bot-commands",
    "post-ap-math", "higher-cs", "higher-other",
    "aphome-econ", "apresearch", "apart-design"
]

essential_channels = [
    "apgov-us", "apchem", "apspanish-lit",
    "apchinese", "apes", "appsych",
    "aplit", "apgov-comp", "apcsa",
    "aphug", "apmacro", "apseminar", "apstats",
    "apeuro", "apush", "aparthistory", "apmicro",
    "apcalc-ab", "apcalc-bc", "apcsp", "apitalian",
    "aplang", "apjapanese", "apphysicsc-mech", "apphysicsc-em",
    "apspanish-lang", "apbio", "apfrench", "apwh-modern", "apphysics1",
    "apgerman", "apmusictheory", "aplatin", "apphysics2",
    "general-1", "school-advice", "emotional-support", "non-ap-help"
]

class DayZeroComplete(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='lock_nonessential', description='Restrict access to non-essential channels.')
    @app_commands.checks.has_permissions(administrator=True)
    async def lock_nonessential(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        staff_role = discord.utils.get(guild.roles, name="Staff")
        everyone_role = guild.default_role

        locked_channels = []
        failed_channels = []

        for category in guild.categories:
            if category.name == "Events":
                for channel in category.channels:
                    try:
                        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                            overwrite = channel.overwrites_for(everyone_role)
                            overwrite.view_channel = False
                            if isinstance(channel, discord.TextChannel):
                                overwrite.send_messages = False
                            elif isinstance(channel, discord.VoiceChannel):
                                overwrite.connect = False

                            await channel.set_permissions(everyone_role, overwrite=overwrite)

                            staff_overwrite = channel.overwrites_for(staff_role)
                            staff_overwrite.view_channel = True
                            if isinstance(channel, discord.TextChannel):
                                staff_overwrite.send_messages = True
                            elif isinstance(channel, discord.VoiceChannel):
                                staff_overwrite.connect = True

                            await channel.set_permissions(staff_role, overwrite=staff_overwrite)

                            locked_channels.append(channel.name)
                    except Exception as e:
                        failed_channels.append((channel.name, str(e)))

            elif category.name == "Lounge":
                for channel in category.channels:
                    if isinstance(channel, discord.TextChannel):
                        try:
                            overwrite = channel.overwrites_for(everyone_role)
                            overwrite.view_channel = False
                            overwrite.send_messages = False
                            await channel.set_permissions(everyone_role, overwrite=overwrite)

                            staff_overwrite = channel.overwrites_for(staff_role)
                            staff_overwrite.view_channel = True
                            staff_overwrite.send_messages = True
                            await channel.set_permissions(staff_role, overwrite=staff_overwrite)

                            locked_channels.append(channel.name)
                        except Exception as e:
                            failed_channels.append((channel.name, str(e)))

            elif category.name == "Voice Channels":
                for channel in category.channels:
                    if isinstance(channel, discord.VoiceChannel):
                        try:
                            overwrite = channel.overwrites_for(everyone_role)
                            overwrite.connect = False
                            await channel.set_permissions(everyone_role, overwrite=overwrite)

                            staff_overwrite = channel.overwrites_for(staff_role)
                            staff_overwrite.connect = True
                            await channel.set_permissions(staff_role, overwrite=staff_overwrite)

                            locked_channels.append(channel.name)
                        except Exception as e:
                            failed_channels.append((channel.name, str(e)))

        msg = f"🔒 Locked channels: {', '.join(locked_channels)}\n"
        if failed_channels:
            msg += "\n⚠️ Failed to lock:\n" + "\n".join([f"{name} ({error})" for name, error in failed_channels])

        await interaction.followup.send(msg)

    @app_commands.command(name='unlock_nonessential', description='Restore access to non-essential channels.')
    @app_commands.checks.has_permissions(administrator=True)
    async def unlock_nonessential(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        staff_role = discord.utils.get(guild.roles, name="Staff")
        everyone_role = guild.default_role

        unlocked_channels = []
        failed_channels = []

        for category in guild.categories:
            if category.name == "Events":
                for channel in category.channels:
                    try:
                        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                            overwrite = channel.overwrites_for(everyone_role)
                            overwrite.view_channel = True
                            if isinstance(channel, discord.TextChannel):
                                overwrite.send_messages = True
                            elif isinstance(channel, discord.VoiceChannel):
                                overwrite.connect = True
                            await channel.set_permissions(everyone_role, overwrite=overwrite)

                            staff_overwrite = channel.overwrites_for(staff_role)
                            staff_overwrite.view_channel = True
                            if isinstance(channel, discord.TextChannel):
                                staff_overwrite.send_messages = True
                            elif isinstance(channel, discord.VoiceChannel):
                                staff_overwrite.connect = True
                            await channel.set_permissions(staff_role, overwrite=staff_overwrite)

                            unlocked_channels.append(channel.name)
                    except Exception as e:
                        failed_channels.append((channel.name, str(e)))

            elif category.name == "Lounge":
                for channel in category.channels:
                    if isinstance(channel, discord.TextChannel):
                        try:
                            overwrite = channel.overwrites_for(everyone_role)
                            overwrite.view_channel = True
                            overwrite.send_messages = True
                            await channel.set_permissions(everyone_role, overwrite=overwrite)

                            staff_overwrite = channel.overwrites_for(staff_role)
                            staff_overwrite.view_channel = True
                            staff_overwrite.send_messages = True
                            await channel.set_permissions(staff_role, overwrite=staff_overwrite)

                            unlocked_channels.append(channel.name)
                        except Exception as e:
                            failed_channels.append((channel.name, str(e)))

            elif category.name == "Voice Channels":
                for channel in category.channels:
                    if isinstance(channel, discord.VoiceChannel):
                        try:
                            overwrite = channel.overwrites_for(everyone_role)
                            overwrite.connect = True
                            await channel.set_permissions(everyone_role, overwrite=overwrite)

                            staff_overwrite = channel.overwrites_for(staff_role)
                            staff_overwrite.connect = True
                            await channel.set_permissions(staff_role, overwrite=staff_overwrite)

                            unlocked_channels.append(channel.name)
                        except Exception as e:
                            failed_channels.append((channel.name, str(e)))

        msg = f"🔓 Unlocked channels: {', '.join(unlocked_channels)}\n"
        if failed_channels:
            msg += "\n⚠️ Failed to unlock:\n" + "\n".join([f"{name} ({error})" for name, error in failed_channels])

        await interaction.followup.send(msg)

    @app_commands.command(name='lock_essential', description='Restrict access to essential channels only to staff.')
    @app_commands.checks.has_permissions(administrator=True)
    async def lock_essential(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        staff_role = discord.utils.get(guild.roles, name="Staff")
        everyone_role = guild.default_role

        locked_channels = []
        failed_channels = []

        for channel_name in essential_channels:
            channel = discord.utils.get(guild.channels, name=channel_name)
            if not channel:
                failed_channels.append((channel_name, "Channel not found"))
                continue

            try:
                overwrite = channel.overwrites_for(everyone_role)
                staff_overwrite = channel.overwrites_for(staff_role)

                if isinstance(channel, discord.TextChannel):
                    overwrite.view_channel = False
                    overwrite.send_messages = False
                    staff_overwrite.view_channel = True
                    staff_overwrite.send_messages = True

                elif isinstance(channel, discord.VoiceChannel):
                    overwrite.connect = False
                    staff_overwrite.connect = True

                await channel.set_permissions(everyone_role, overwrite=overwrite)
                await channel.set_permissions(staff_role, overwrite=staff_overwrite)

                locked_channels.append(channel.name)
            except Exception as e:
                failed_channels.append((channel_name, str(e)))

        msg = f"🔒 Locked essential channels: {', '.join(locked_channels)}\n"
        if failed_channels:
            msg += "\n⚠️ Failed to lock:\n" + "\n".join([f"{name} ({error})" for name, error in failed_channels])

        await interaction.followup.send(msg)


    @app_commands.command(name='reopen_channels', description='Reopen AP channels based on date proximity and essential status.')
    @app_commands.checks.has_permissions(administrator=True)
    async def reopen_channels(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        # Define the exam schedule
        exam_schedule_by_date = {
            "Monday, May 5, 2025": ["apbio", "aplatin", "apeuro", "apmicro"],
            "Tuesday, May 6, 2025": ["apchem", "aphug", "apgov-us"],
            "Wednesday, May 7, 2025": ["aplit", "apgov-comp", "apcsa"],
            "Thursday, May 8, 2025": ["apstats", "apjapanese", "apwh-modern"],
            "Friday, May 9, 2025": ["apitalian", "apush", "apchinese", "apmacro"],
            "Monday, May 12, 2025": ["apcalc-ab", "apcalc-bc", "apmusictheory", "apseminar"],
            "Tuesday, May 13, 2025": ["apfrench", "apes", "apphysics2"],
            "Wednesday, May 14, 2025": ["aplang", "apgerman", "apphysicsc-mech"],
            "Thursday, May 15, 2025": ["aparthistory", "apspanish-lang", "apcsp", "apphysicsc-em"],
            "Friday, May 16, 2025": ["apphysics1", "apspanish-lit", "appsych"]
        }

        # Format schedule keys for comparison
        formatted_schedule = {}
        for full_date, channels in exam_schedule_by_date.items():
            dt = datetime.strptime(full_date, "%A, %B %d, %Y")
            key = f"{dt.strftime('%B')} {dt.day}, {dt.year}"  # e.g. "May 5, 2025"
            formatted_schedule[key] = channels

        today = datetime.today()
        essential_channels = {
            "general-1", "school-advice", "emotional-support", "non-ap-help"
        }
        channels_to_reopen = set(essential_channels)

        for date_str, channels in formatted_schedule.items():
            exam_date = datetime.strptime(date_str, "%B %d, %Y")
            days_diff = (today - exam_date).days
            if exam_date >= today or (0 <= days_diff <= 2):
                channels_to_reopen.update(channels)

        guild = interaction.guild
        everyone_role = guild.default_role
        reopened = []
        failed = []

        for name in channels_to_reopen:
            channel = discord.utils.get(guild.text_channels, name=name)
            if channel:
                try:
                    await channel.set_permissions(everyone_role, send_messages=True, read_messages=True)
                    reopened.append(f"✅ #{channel.name}")
                except Exception as e:
                    failed.append(f"⚠️ {channel.name}: {str(e)}")
            else:
                failed.append(f"❌ Not found: {name}")

        response = "🔓 Channels reopened:\n" + "\n".join(reopened)
        if failed:
            response += "\n\n⚠️ Errors:\n" + "\n".join(failed)

        await interaction.followup.send(response)

# Setup function to load cog
async def setup(bot: commands.Bot):
    await bot.add_cog(DayZeroComplete(bot), guilds=[discord.Object(id=bot.guild_id)])
