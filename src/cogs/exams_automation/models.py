import nextcord
import datetime

red = 0xff0000
green = 0x00ff00

essential_generals = ['general-1', 'school-advice', 'emotional-support', 'non-ap-help']
nonessential_textchannels = ["welcome", "general-2", "college", "bot-commands",
                             "post-ap-math", "higher-cs", "higher-other",
                             "aphome-econ", "apresearch", "apart-design"]

subject_channels = [["apgov-us", "aparthistory", "apchem", None],
                    ["aphug", "apmicro", "apseminar", "apstats"],
                    ["aplit", "apgov-comp", "apcsa", None],
                    ["apchinese", "apes", "appsych", None],
                    ["apeuro", "apush", "apmacro", "apspanish-lit"],
                    ["apcalc-ab", "apcalc-bc", "apitalian", "apprecalc"],
                    ["aplang", "apafam-studies", "apphysicsc-mech", "apphysicsc-em"],
                    ["apfrench", "apwh-modern", "apcsp", "apmusictheory"],
                    ["apspanish-lang", "apbio", "apjapanese", None],
                    ["apgerman", "apphysics1", "aplatin", "apphysics2"]]


class APChannel:

    def __init__(self, guild, channel_name):
        self.channel = nextcord.utils.get(guild.channels, name=channel_name)
        self.guild = guild

    def ap_roles(self):

        ap_roles = [role for role in self.channel.overwrites if isinstance(role, nextcord.Role) and
                    ((role.color == nextcord.Colour.blue() or role.color == nextcord.Color(0x94dfa2)) or
                    ("ap " in role.name.lower()) or
                    (role.name == "Post-AP Math" or role.name == "Higher CS" or role.name == "Higher Other"))]

        if not ap_roles:
            ap_roles = [self.guild.default_role]

        return ap_roles

    def create_embed(self):
        embed = nextcord.Embed(title="")
        return embed

    async def shutdown(self):

        ap_roles = self.ap_roles()
        for role in ap_roles:
            await self.channel.set_permissions(role, read_messages=False)

        shutdown_embed = self.create_embed()
        shutdown_embed.colour = red
        shutdown_embed.add_field(name='', value=f"Shutting down {self.channel.mention}.")
        shutdown_embed.timestamp = datetime.datetime.now()

        await self.channel.send(embed=shutdown_embed)

    async def open(self):

        ap_roles = self.ap_roles()
        for role in ap_roles:
            generals = nextcord.utils.get(self.guild.categories, name="General Channels")
            if self.channel not in generals.channels:
                await self.channel.set_permissions(role, read_messages=True)
            else:
                await self.channel.set_permissions(role, read_messages=None)

        open_embed = self.create_embed()
        open_embed.colour = green
        open_embed.add_field(name='', value=f"Reopening {self.channel.mention}.")
        open_embed.timestamp = datetime.datetime.now()

        await self.channel.send(embed=open_embed)


class APServer:

    def __init__(self, guild):
        self.guild = guild

    async def shutdown(self):

        for channel_name in essential_generals:
            channel = APChannel(self.guild, channel_name)
            await channel.shutdown()

        ap_channels = nextcord.utils.get(self.guild.categories, name="Subject Channels")
        for channel in ap_channels.channels:
            ap_channel = APChannel(self.guild, channel.name)
            await ap_channel.shutdown()

        subject_channels.pop(0)

        voice_channels = nextcord.utils.get(self.guild.categories, name="Voice Channels")
        for channel in voice_channels.channels:
            voice_channel = APChannel(self.guild, channel.name)
            await voice_channel.shutdown()

        misc_channels = nextcord.utils.get(self.guild.categories, name="AP 2024 Exam Season")
        for channel in misc_channels.channels:
            if not channel.name == "ap-exam-info-2023":
                misc_channel = APChannel(self.guild, channel.name)
                await misc_channel.shutdown()

    async def open(self):

        for channel_name in essential_generals:
            channel = APChannel(self.guild, channel_name)
            await channel.open()

        for testing_day in subject_channels:
            for channel_name in testing_day:
                if not channel_name:
                    continue
                subject_channel = APChannel(self.guild, channel_name)
                await subject_channel.open()

        misc_channels = nextcord.utils.get(self.guild.categories, name="AP 2024 Exam Season")
        for channel in misc_channels.channels:
            if not channel.name == "ap-exam-info-2023":
                misc_channel = APChannel(self.guild, channel.name)
                await misc_channel.open()