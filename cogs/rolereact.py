import discord
from discord.ext import commands

blue = 0x00ffff

# This is without a doubt perhaps the worst way to do this, but I am lazy.
# Basically just a View class per role category with buttons for each role.
# Also self-persistent!


class Arts(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Studio Art 2D', style=discord.ButtonStyle.grey, custom_id='Studio Art 2D',
                       emoji="<:2DArt:614310804761608207>", row=0)
    async def studioart2d(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP 2D Art and Design")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Studio Art 3D', style=discord.ButtonStyle.grey, custom_id='Studio Art 3D',
                       emoji='<:3DArt:1061485699972464670>', row=1)
    async def studioart3d(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP 3D Art and Design")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Drawing', style=discord.ButtonStyle.grey, custom_id='Drawing',
                       emoji="<:Drawing:1061486284234821743>", row=2)
    async def drawing(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Drawing")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Art History', style=discord.ButtonStyle.grey, custom_id='Art History',
                       emoji='<:ArtHistory:1061485761960087552>', row=0)
    async def arthistory(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Art History")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Music Theory', style=discord.ButtonStyle.grey, custom_id='Music Theory',
                       emoji='<:MusicTheory:1061486683201208511>', row=1)
    async def musictheory(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Music Theory")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class English(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Literature', style=discord.ButtonStyle.grey, custom_id='Literature',
                       emoji='<:EnglishLiterature:1061486349015851038>', row=0)
    async def literature(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP English Lit")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Language', style=discord.ButtonStyle.grey, custom_id='Language',
                       emoji='<:EnglishLanguage:1061486335245951086>', row=1)
    async def language(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP English Lang")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Seminar', style=discord.ButtonStyle.grey, custom_id='Seminar',
                       emoji='<:Seminar:1061486772825100429>', row=0)
    async def seminar(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Seminar")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Research', style=discord.ButtonStyle.grey, custom_id='Research',
                       emoji='<:Research:1061486754646990898>', row=1)
    async def research(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Research")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class Languages(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Japanese', style=discord.ButtonStyle.grey, custom_id='Japanese',
                       emoji='<:Japanese:1061486555199447040>', row=0)
    async def japanese(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Japanese")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Italian', style=discord.ButtonStyle.grey, custom_id='Italian',
                       emoji='<:Italian:1061486542369075200>', row=0)
    async def italian(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Italian")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Chinese', style=discord.ButtonStyle.grey, custom_id='Chinese',
                       emoji='<:Chinese:1061486236109394020>', row=0)
    async def chinese(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Chinese")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Latin', style=discord.ButtonStyle.grey, custom_id='Latin',
                       emoji='<:Latin:1061486569162280990>', row=1)
    async def latin(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Latin")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='German', style=discord.ButtonStyle.grey, custom_id='German',
                       emoji='<:German:1061486440904667186>', row=1)
    async def german(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP German")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='French', style=discord.ButtonStyle.grey, custom_id='French',
                       emoji='<:French:1061486415361347705>', row=1)
    async def french(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP French")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Spanish Lang', style=discord.ButtonStyle.grey, custom_id='Spanish Lang',
                       emoji='<:SpanishLanguage:1061486827539795998>', row=2)
    async def spanish_lang(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Spanish Lang")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Spanish Lit', style=discord.ButtonStyle.grey, custom_id='Spanish Lit',
                       emoji='<:SpanishLiterature:1061486844807762000>', row=2)
    async def spanish_lit(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Spanish Lit")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class MathCS(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Precalc', style=discord.ButtonStyle.grey, custom_id='Precalc',
                       emoji='<:precalc:1061804037915279460>', row=0)
    async def precalc(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Precalculus")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Calc AB', style=discord.ButtonStyle.grey, custom_id='Calc AB',
                       emoji='<:CalculusAB:1061486117397995530>', row=1)
    async def calcab(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Calc AB")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Calc BC', style=discord.ButtonStyle.grey, custom_id='Calc BC',
                       emoji='<:CalculusBC:1061486180853616720>', row=2)
    async def calcbc(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Calc BC")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Stats', style=discord.ButtonStyle.grey, custom_id='Stats',
                       emoji='<:Statistics:1061486861790482563>', row=0)
    async def stats(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Stats")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Comp Sci A', style=discord.ButtonStyle.grey, custom_id='Comp Sci A',
                       emoji='<:CSA:1061485898895724615>', row=1)
    async def compscia(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP CompSci A")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Comp Sci Prin', style=discord.ButtonStyle.grey, custom_id='Comp Sci Prin',
                       emoji='<:CSP:1061486067016015892>', row=2)
    async def compsciprin(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP CompSci Prin")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class Sciences(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Physics 1', style=discord.ButtonStyle.grey, custom_id='Physics 1',
                       emoji='<:Physics1:1061486700485955644>', row=0)
    async def physics1(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Physics 1")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Physics 2', style=discord.ButtonStyle.grey, custom_id='Physics 2',
                       emoji='<:Physics2:1061486719960096890>', row=1)
    async def physics2(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Physics 2")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Chemistry', style=discord.ButtonStyle.grey, custom_id='Chemistry',
                       emoji='<:Chemistry:1061486200810131476>', row=2)
    async def chemistry(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Chem")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Mech', style=discord.ButtonStyle.grey, custom_id='Mech',
                       emoji='<:Mechanics:1061486622446731354>', row=0)
    async def mech(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Physics C Mech")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='E/M', style=discord.ButtonStyle.grey, custom_id='E/M',
                       emoji='<:EM:1061486300995268658>', row=1)
    async def em(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Physics C E/M")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Enviro', style=discord.ButtonStyle.grey, custom_id='Enviro',
                       emoji='<:EnvironmentalScience:1061486372541698099>', row=0)
    async def enviro(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Environ Sci")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Biology', style=discord.ButtonStyle.grey, custom_id='Biology',
                       emoji='<:Biology:1061485856868794368>', row=1)
    async def biology(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Biology")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class SocialStudies(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Comp Gov', style=discord.ButtonStyle.grey, custom_id='Comp Gov',
                       emoji='<:ComparativeGovernment:1061486253192781865>', row=0)
    async def compgov(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Comparative Government")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='World M', style=discord.ButtonStyle.grey, custom_id='World M',
                       emoji='<:ModernWorldHistory:1061486662284222525>', row=1)
    async def worldm(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP World History: Modern")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Human Geo', style=discord.ButtonStyle.grey, custom_id='Human Geo',
                       emoji='<:HumanGeography:1061486512585314325>', row=2)
    async def humangeo(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Human Geo")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='US Gov', style=discord.ButtonStyle.grey, custom_id='US Gov',
                       emoji='<:USGovernment:1061486879884722206>', row=0)
    async def usgov(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP US Gov")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='APUSH', style=discord.ButtonStyle.grey, custom_id='APUSH',
                       emoji='<:USHistory:1061486902903054386>', row=1)
    async def apush(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP US History")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Micro', style=discord.ButtonStyle.grey, custom_id='Micro',
                       emoji='<:Microeconomics:1061486644559089724>', row=2)
    async def micro(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Micro")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Psych', style=discord.ButtonStyle.grey, custom_id='Psych',
                       emoji='<:Psychology:1061486737857183774>', row=0)
    async def psych(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Psych")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Euro', style=discord.ButtonStyle.grey, custom_id='Euro',
                       emoji='<:EuropeanHistory:1061486395455180832>', row=1)
    async def euro(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Euro")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Macro', style=discord.ButtonStyle.grey, custom_id='Macro',
                       emoji='<:Macroeconomics:1061486600267251732>', row=2)
    async def macro(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="AP Macro")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class PostAP(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Post-AP Math', style=discord.ButtonStyle.grey, custom_id='Post-AP Math',
                       emoji='<:postapmath:1061801588508872794>')
    async def postapmath(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Post-AP Math")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Higher CS', style=discord.ButtonStyle.grey, custom_id='Higher CS',
                       emoji='<:highercs:1061801585312804924>')
    async def highercs(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Higher CS")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Higher Other', style=discord.ButtonStyle.grey, custom_id='Higher Other',
                       emoji='<:higherother:1061801586453643265>')
    async def higherother(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Higher Other")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class Pronouns(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='she/her', style=discord.ButtonStyle.grey, custom_id='she',
                       emoji='<:sheher:1061486974055227492>', row=0)
    async def she(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="she/her/hers")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='he/him', style=discord.ButtonStyle.grey, custom_id='he',
                       emoji='<:hehim:1061486951875760241>', row=1)
    async def he(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="he/him/his")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='they/them', style=discord.ButtonStyle.grey, custom_id='they',
                       emoji='<:theythem:1061486997576892416>', row=0)
    async def they(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="they/them/theirs")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Ask me!', style=discord.ButtonStyle.grey, custom_id='ask',
                       emoji='<:askme:1061803381804507257>', row=1)
    async def ask(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Ask me for my pronouns!")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class Booster(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='nitro-a', style=discord.ButtonStyle.grey, custom_id='A', row=0)
    async def nitroa(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="nitro-a")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            for role_check in member.roles:
                if "nitro" in role_check.name:
                    await member.remove_roles(role_check)
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='nitro-b', style=discord.ButtonStyle.grey, custom_id='b', row=1)
    async def nitrob(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="nitro-b")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            for role_check in member.roles:
                if "nitro" in role_check.name:
                    await member.remove_roles(role_check)
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='nitro-c', style=discord.ButtonStyle.grey, custom_id='C', row=2)
    async def nitroc(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="nitro-c")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            for role_check in member.roles:
                if "nitro" in role_check.name:
                    await member.remove_roles(role_check)
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='nitro-d', style=discord.ButtonStyle.grey, custom_id='D', row=0)
    async def nitrod(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="nitro-d")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            for role_check in member.roles:
                if "nitro" in role_check.name:
                    await member.remove_roles(role_check)
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='nitro-e', style=discord.ButtonStyle.grey, custom_id='E', row=1)
    async def nitroe(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="nitro-e")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            for role_check in member.roles:
                if "nitro" in role_check.name:
                    await member.remove_roles(role_check)
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='nitro-f', style=discord.ButtonStyle.grey, custom_id='F', row=2)
    async def nitrof(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="nitro-f")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            for role_check in member.roles:
                if "nitro" in role_check.name:
                    await member.remove_roles(role_check)
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class LoungeOne(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Anime-Manga', style=discord.ButtonStyle.grey, custom_id='anime-manga',
                       emoji='🍡', row=0)
    async def animemanga(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Anime & Manga")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Art', style=discord.ButtonStyle.grey, custom_id='art',
                       emoji='🖌', row=1)
    async def art(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Art")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Books-Writing', style=discord.ButtonStyle.grey, custom_id='books-writing',
                       emoji='📚', row=2)
    async def bookswriting(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Books & Writing")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Events', style=discord.ButtonStyle.grey, custom_id='events',
                       emoji='🎉', row=0)
    async def events(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Events")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Fashion', style=discord.ButtonStyle.grey, custom_id='fashion',
                       emoji='👓', row=1)
    async def fashion(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Fashion")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Film-TV', style=discord.ButtonStyle.grey, custom_id='film-tv',
                       emoji='📽', row=2)
    async def filmtv(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Film & TV")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class LoungeTwo(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Food', style=discord.ButtonStyle.grey, custom_id='food',
                       emoji='🥘', row=0)
    async def food(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Food")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Gaming', style=discord.ButtonStyle.grey, custom_id='gaming',
                       emoji='🎮', row=1)
    async def gaming(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Gaming")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Languages', style=discord.ButtonStyle.grey, custom_id='languages',
                       emoji='🌐', row=2)
    async def languages(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Languages")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Music', style=discord.ButtonStyle.grey, custom_id='music',
                       emoji='🎵', row=0)
    async def music(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Music")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Pets', style=discord.ButtonStyle.grey, custom_id='pets',
                       emoji='🐱', row=1)
    async def pets(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Pets")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Photography', style=discord.ButtonStyle.grey, custom_id='photography',
                       emoji='📷', row=2)
    async def photography(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Photography")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class LoungeThree(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Sports', style=discord.ButtonStyle.grey, custom_id='sports',
                       emoji='🏀', row=0)
    async def sports(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Sports")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Tech', style=discord.ButtonStyle.grey, custom_id='tech',
                       emoji='🖥️', row=0)
    async def tech(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Tech")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @discord.ui.button(label='Opt-Out of Lounge', style=discord.ButtonStyle.red, custom_id='languages', row=1)
    async def optout(self, interaction, button):

        role = discord.utils.get(interaction.guild.roles, name="Lounge: Opt-Out")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class RoleReact(commands.Cog):
    """Role React"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot


async def setup(bot):
    await bot.add_cog(RoleReact(bot), guilds=[discord.Object(id=bot.guild_id)])
    bot.add_view(Arts(bot))
    bot.add_view(English(bot))
    bot.add_view(Languages(bot))
    bot.add_view(MathCS(bot))
    bot.add_view(Sciences(bot))
    bot.add_view(SocialStudies(bot))
    bot.add_view(PostAP(bot))
    bot.add_view(Pronouns(bot))
    bot.add_view(Booster(bot))
    bot.add_view(LoungeOne(bot))
    bot.add_view(LoungeTwo(bot))
    bot.add_view(LoungeThree(bot))
