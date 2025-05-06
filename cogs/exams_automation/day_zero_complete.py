import discord
from discord.ext import tasks, commands

import datetime
from cogs.exams_automation.models import APChannel, APServer

red = 0xff0000
green = 0x00ff00

nonessential_textchannels = ["general-2", "college", "bot-commands",
                             "post-ap-math", "higher-cs", "higher-other",
                             "aphome-econ", "apresearch", "apart-design"]

subject_channels = [["apbio", "aplatin", "apeuro", "apmicro"],
                    ["apchem", "aphug", "apgov-us", None],
                    ["aplit", "apgov-comp", "apcsa", None],
                    ["apstats", "apjapanese", "apwh-modern", None],
                    ["apitalian", "apush", "apchinese", "apmacro"],
                    ["apcalc-ab", "apcalc-bc", "apmusictheory", "apseminar"],
                    ["apfrench", "apes", "apphysics2", "apprecalc"],
                    ["aplang", "apgerman", "apphysicsc-mech", None],
                    ["aparthistory", "apspanish-lang", "apcsp", "apphysicsc-em"],
                    ["apphysics1", "apspanish-lit", "appsych", None]]

study_session_vc_id = [1368779387327217694, 1368779432315064350, 1368779507359682641, 1368779558903349338]

class DayZero(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.dayzero.start()

    @tasks.loop(seconds=1, count=1)
    async def dayzero(self):
        guild = self.bot.get_guild(self.bot.guild_id)

        for channel_name in nonessential_textchannels:
            channel = APChannel(guild, channel_name)
            await channel.shutdown()

        lounge = discord.utils.get(guild.categories, name="Lounge")
        for channel in lounge.channels:
            if channel.name == "lounge-signup":
                continue
            lounge_channel = APChannel(guild, channel.name)
            await lounge_channel.shutdown()

        events = discord.utils.get(guild.categories, name="Events")
        for channel in events.channels:
            events_channel = APChannel(guild, channel.name)
            await events_channel.shutdown()

        # Disable all VCs in the "Voice Channel" category
        voice_category = discord.utils.get(guild.categories, name="Voice Channel")
        if voice_category:
            for channel in voice_category.channels:
                if isinstance(channel, discord.VoiceChannel):
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.connect = False
                    overwrite.send_messages = False  # for stage/chat VCs
                    await channel.set_permissions(guild.default_role, overwrite=overwrite)

    @dayzero.before_loop
    async def pre_dayzero(self):
        shutdown_date = datetime.datetime(year=2025, month=5, day=5, hour=7, minute=50, second=00)
        await discord.utils.sleep_until(shutdown_date)

class DayOne(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 1

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=5, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(guild)
        await apserver.open(0)

        i = 0
        for channel_name in subject_channels[1]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(guild, channel_name)
                name = [role.name for role in channel.ap_roles() if "ap " in role.name.lower() and "teacher" not in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(guild.default_role, read_messages=None)
                i += 1
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(guild.default_role, read_messages=None)
                i += 1

    @end.before_loop
    async def pre_end(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=5, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)

class DayTwo(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 2

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=6, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(guild)
        await apserver.open(0,1)

        i = 0
        for channel_name in subject_channels[2]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(guild, channel_name)
                name = [role.name for role in channel.ap_roles()
                        if "ap " in role.name.lower() and "teacher" not in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(guild.default_role, read_messages=None)
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(guild.default_role, read_messages=None)
            i += 1

    @end.before_loop
    async def pre_end(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=6, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)


class DayThree(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 3

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=7, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open(1,2)
        i = 0
        for channel_name in subject_channels[self.n]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])

            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()
                        if "ap " in role.name.lower() and "teacher" not in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)

            i += 1

    @end.before_loop
    async def pre_end(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=7, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)



class DayFour(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 4

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=8, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open(2,3)

        i = 0
        for idx, channel_name in enumerate(subject_channels[self.n]):
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])

            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()
                        if "ap " in role.name.lower() and "teacher" not in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)

            i += 1

    @end.before_loop
    async def pre_end(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=8, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)

class DayFive(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 5

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=9, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open(3,4)

        i = 0
        for idx, channel_name in enumerate(subject_channels[self.n]):
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])

            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()
                        if "ap " in role.name.lower() and "teacher" not in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)

            i += 1

    @end.before_loop
    async def pre_end(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=9, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)

class DaySix(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.end.start()
        self.n = 6

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.open(4)

    @end.before_loop
    async def pre_end(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=10, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)


class DaySeven(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.end.start()
        self.n = 7

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.open()

    @end.before_loop
    async def pre_end(self):
        await self.bot.wait_until_ready()
        date = datetime.datetime(year=2025, month=5, day=11, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)



class DayEight(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 8

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2025, month=5, day=12, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open(5)
        i = 0
        for channel_name in subject_channels[6]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles() if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            i += 1

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2025, month=5, day=12, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)


class DayNine(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 9

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2025, month=5, day=13, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open(5,6)
        i = 0
        for channel_name in subject_channels[7]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles() if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            i += 1
    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2025, month=5, day=13, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)


class DayTen(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 10

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2025, month=5, day=14, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open(6,7)
        i = 0
        for channel_name in subject_channels[8]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles() if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            i += 1

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2025, month=5, day=14, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)


class DayEleven(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 11

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2025, month=5, day=15, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open(7,8)
        i = 0
        for channel_name in subject_channels[9]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles() if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            else:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
            i += 1

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2025, month=5, day=15, hour=19, minute=00, second=0)
        await discord.utils.sleep_until(date)

class DayTwelve(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.n = 12

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2025, month=5, day=16, hour=8, minute=00, second=00)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open(8,9)

        guild = self.bot.get_guild(self.bot.guild_id)

        for channel_name in nonessential_textchannels:
            channel = APChannel(guild, channel_name)
            await channel.open()

        lounge = discord.utils.get(guild.categories, name="Lounge")
        if lounge:
            for channel in lounge.channels:
                lounge_channel = APChannel(guild, channel.name)
                await lounge_channel.open()

        events = discord.utils.get(guild.categories, name="Events")
        if events:
            for channel in events.channels:
                events_channel = APChannel(guild, channel.name)
                await events_channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2025, month=5, day=16, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)


class DayThirteen(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.end.start()
        self.n = 13

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.open(9)

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2025, month=5, day=17, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)

class DayFourteen(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.end.start()
        self.n = 14

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        self.guild = self.bot.get_guild(self.bot.guild_id)
        apserver = APServer(self.guild)
        await apserver.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2025, month=5, day=18, hour=19, minute=00, second=00)
        await discord.utils.sleep_until(date)



async def setup(bot):
    await bot.add_cog(DayZero(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayOne(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayTwo(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayThree(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayFour(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayFive(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DaySix(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DaySeven(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayEight(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayNine(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayTen(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayEleven(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayTwelve(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayThirteen(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayFourteen(bot), guilds=[discord.Object(id=bot.guild_id)])







