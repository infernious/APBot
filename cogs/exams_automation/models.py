import discord
import datetime

red = 0xff0000
green = 0x00ff00

essential_generals = ['general-1', 'school-advice', 'emotional-support', 'non-ap-help']
nonessential_textchannels = ["general-2", "college", "bot-commands",
                             "post-ap-math", "higher-cs", "higher-other",
                             "aphome-econ", "apresearch", "apart-design"]


class APChannel:

    def __init__(self, guild, channel_name):
        self.channel = discord.utils.get(guild.channels, name=channel_name)
        self.guild = guild

    def ap_roles(self):
        ap_roles = [role for role in self.channel.overwrites if isinstance(role, discord.Role) and
                    ((role.color == discord.Colour.blue() or role.color == discord.Color(0x94dfa2)) or
                     ("ap " in role.name.lower()) or
                     (role.name == "Post-AP Math" or role.name == "Higher CS" or role.name == "Higher Other")) and "teacher" not in role.name.lower()]

        if not ap_roles:
            ap_roles = [self.guild.default_role]

        return ap_roles

    def create_embed(self):
        return discord.Embed(title="")

    async def shutdown(self):
        ap_roles = self.ap_roles()
        for role in ap_roles:
            await self.channel.set_permissions(role, read_messages=False)

        if isinstance(self.channel, discord.TextChannel):
            shutdown_embed = self.create_embed()
            shutdown_embed.colour = red
            shutdown_embed.add_field(name='', value=f"Shutting down {self.channel.mention}.")
            shutdown_embed.timestamp = datetime.datetime.now()
            await self.channel.send(embed=shutdown_embed)

    async def open(self):
        ap_roles = self.ap_roles()
        for role in ap_roles:
            generals = discord.utils.get(self.guild.categories, name="General Channels")
            if self.channel not in generals.channels:
                await self.channel.set_permissions(role, read_messages=True)
            else:
                await self.channel.set_permissions(role, read_messages=None)
        if isinstance(self.channel, discord.TextChannel):
            open_embed = self.create_embed()
            open_embed.colour = green
            open_embed.add_field(name='', value=f"Reopening {self.channel.mention}.")
            open_embed.timestamp = datetime.datetime.now()
            await self.channel.send(embed=open_embed)

class APServer:

    def __init__(self, guild):
        self.guild = guild

    async def shutdown(self):
        # Shutdown essential general channels except those to keep open
        for channel_name in essential_generals:
            if channel_name not in ["ap-exam-announcements-2025", "help-i-cant-see-channels"]:
                channel = APChannel(self.guild, channel_name)
                await channel.shutdown()
        
        lecture_stages_category = discord.utils.get(self.guild.categories, name="Lecture Stages")
        if lecture_stages_category:
            for channel in lecture_stages_category.channels:
                stage_channel = APChannel(self.guild, channel.name)
                await stage_channel.shutdown()


        # Shutdown subject channels
        ap_channels = discord.utils.get(self.guild.categories, name="Subject Channels")
        if ap_channels:
            for channel in ap_channels.channels:
                ap_channel = APChannel(self.guild, channel.name)
                await ap_channel.shutdown()

        # Shutdown voice channels
        voice_channels = discord.utils.get(self.guild.categories, name="Voice Channels")
        if voice_channels:
            for channel in voice_channels.channels:
                voice_channel = APChannel(self.guild, channel.name)
                await voice_channel.shutdown()

        # Shutdown other misc channels under AP Season 2025
        misc_channels = discord.utils.get(self.guild.categories, name="AP Season 2025")
        if misc_channels:
            for channel in misc_channels.channels:
                if channel.name not in ["ap-exam-announcements-2025", "help-i-cant-see-channels"]:
                    misc_channel = APChannel(self.guild, channel.name)
                    await misc_channel.shutdown()

        # Shutdown all channels in the Events category
        events_category = discord.utils.get(self.guild.categories, name="Events")
        if events_category:
            for channel in events_category.channels:
                event_channel = APChannel(self.guild, channel.name)
                await event_channel.shutdown()

    async def open(self, *indices):
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
        # Open essential general channels
        for channel_name in essential_generals:
            channel = APChannel(self.guild, channel_name)
            await channel.open()

        # Open subject channels
        for index in sorted(indices,  reverse=True):
            subject_channels.pop(index)
        for testing_day in subject_channels:
            for channel_name in testing_day:
                if not channel_name:
                    continue
                subject_channel = APChannel(self.guild, channel_name)
                await subject_channel.open()

        lecture_stages_category = discord.utils.get(self.guild.categories, name="Lecture Stages")
        if lecture_stages_category:
            for channel in lecture_stages_category.channels:
                stage_channel = APChannel(self.guild, channel.name)
                await stage_channel.open()


        # Open misc channels under AP Season 2025
        misc_channels = discord.utils.get(self.guild.categories, name="AP Season 2025")
        if misc_channels:
            for channel in misc_channels.channels:
                if channel.name not in ["ap-exam-announcements-2025", "help-i-cant-see-channels"]:
                    misc_channel = APChannel(self.guild, channel.name)
                    await misc_channel.open()
