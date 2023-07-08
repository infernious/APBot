import discord
from discord.ext import tasks, commands

import datetime
from cogs.exams_automation.models import APChannel, APServer

red = 0xff0000
green = 0x00ff00

nonessential_textchannels = ["welcome", "general-2", "college", "bot-commands",
                             "post-ap-math", "higher-cs", "higher-other",
                             "aphome-econ", "apresearch", "apart-design"]

subject_channels = [["apgov-us", "apchem", "apspanish-lit", None],
                    ["apchinese", "apes", "appsych", None],
                    ["aplit", "apgov-comp", "apcsa", None],
                    ["aphug", "apmacro", "apseminar", "apstats"],
                    ["apeuro", "apush", "aparthistory", "apmicro"],
                    ["apcalc-ab", "apcalc-bc", "apcsp", "apitalian"],
                    ["aplang", "apjapanese", "apphysicsc-mech", "apphysicsc-em"],
                    ["apspanish-lang", "apbio", None, None],
                    ["apfrench", "apwh-modern", "apphysics1", None],
                    ["apgerman", "apmusictheory", "aplatin", "apphysics2"]]

study_session_vc_id = [1085333845152379019, 1085333845152379020, 1085333845399851172, 1085333845399851173]


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


    @dayzero.before_loop
    async def pre_dayzero(self):
        shutdown_date = datetime.datetime(year=2023, month=4, day=30, hour=23, minute=59, second=59)
        await discord.utils.sleep_until(shutdown_date)


class DayOne(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 1

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayTwo(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 2

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=18, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayThree(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 3

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

        for i in range(self.n - 2):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayFour(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 4

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

        for i in range(self.n - 2):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayFive(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 5

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

        for i in range(self.n - 2):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DaySeven(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 7

    @tasks.loop(seconds=1, count=1)
    async def end(self):

        i = 0
        for channel_name in subject_channels[self.n - 1]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

        for i in range(self.n - 3):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=18, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayEight(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 8

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n - 1]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

        for i in range(self.n - 3):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayNine(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 9

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n - 1]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

        for i in range(self.n - 3):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=30, second=0)
        await discord.utils.sleep_until(date)


class DayTen(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 10

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n - 1]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

        for i in range(self.n - 3):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayEleven(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 11

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        i = 0
        for channel_name in subject_channels[self.n - 1]:
            study_session_vc = self.bot.get_channel(study_session_vc_id[i])
            if channel_name:
                channel = APChannel(self.guild, channel_name)
                name = [role.name for role in channel.ap_roles()  if "ap " in role.name.lower()]
                await study_session_vc.edit(name=name[0])
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=None)
                i += 1
            if not channel_name:
                await study_session_vc.edit(name=f"Study Session {i + 1}")
                await study_session_vc.set_permissions(self.guild.default_role, read_messages=False)

        for i in range(self.n - 3):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayTwelve(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.beginning.start()
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 12

    @tasks.loop(seconds=1, count=1)
    async def beginning(self):
        apserver = APServer(self.guild)
        await apserver.shutdown()

    @beginning.before_loop
    async def pre_beginning(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=8, minute=0, second=0)
        await discord.utils.sleep_until(date)

    @tasks.loop(seconds=1, count=1)
    async def end(self):
        apserver = APServer(self.guild)
        await apserver.open()

        for i in range(self.n - 3):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

        guild = self.bot.get_guild(self.bot.guild_id)

        for channel_name in nonessential_textchannels:
            channel = APChannel(guild, channel_name)
            await channel.open()

        lounge = discord.utils.get(guild.categories, name="Lounge")
        for channel in lounge.channels:
            lounge_channel = APChannel(guild, channel.name)
            await lounge_channel.open()

        events = discord.utils.get(guild.categories, name="Events")
        for channel in events.channels:
            events_channel = APChannel(guild, channel.name)
            await events_channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayThirteen(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 13

    @tasks.loop(seconds=1, count=1)
    async def end(self):

        for i in range(self.n - 3):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


class DayFourteen(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.end.start()
        self.guild = bot.get_guild(self.bot.guild_id)
        self.n = 14

    @tasks.loop(seconds=1, count=1)
    async def end(self):

        for i in range(self.n - 3):
            for channel_name in subject_channels[i]:
                if not channel_name:
                    continue
                channel = APChannel(self.guild, channel_name)
                await channel.open()

    @end.before_loop
    async def pre_end(self):
        date = datetime.datetime(year=2023, month=5, day=self.n, hour=19, minute=0, second=0)
        await discord.utils.sleep_until(date)


async def setup(bot):
    await bot.add_cog(DayTwo(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayThree(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayFour(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayFive(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DaySeven(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayEight(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayNine(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayTen(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayEleven(bot), guilds=[discord.Object(id=bot.guild_id)])
    await bot.add_cog(DayTwelve(bot), guilds=[discord.Object(id=bot.guild_id)])








