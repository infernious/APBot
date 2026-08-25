import nextcord
from nextcord import slash_command, Interaction
from nextcord.ext import commands, application_checks
from bot_base import APBot
blue = 0x00ffff
from config_handler import Config
config_path = "config.json"
conf = Config(config_path)

ALLOWED_ROLES = ("Admin", "Chat Moderator") 



class Arts(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Studio Art 2D', style=nextcord.ButtonStyle.grey, custom_id='Studio Art 2D',
                       emoji='🎨', row=0)
    async def studioart2d(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP 2D Art and Design")
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message("Member not found in this guild.", ephemeral=True)
            return

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Studio Art 3D', style=nextcord.ButtonStyle.grey, custom_id='Studio Art 3D',
                       emoji='🗿', row=1)
    async def studioart3d(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP 3D Art and Design")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Drawing', style=nextcord.ButtonStyle.grey, custom_id='Drawing',
                       emoji='✏️', row=2)
    async def drawing(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Drawing")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Art History', style=nextcord.ButtonStyle.grey, custom_id='Art History',
                       emoji='🏛️', row=0)
    async def arthistory(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Art History")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Music Theory', style=nextcord.ButtonStyle.grey, custom_id='Music Theory',
                       emoji='🎵', row=1)
    async def musictheory(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Music Theory")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class English(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Literature', style=nextcord.ButtonStyle.grey, custom_id='Literature',
                       emoji='📖', row=0)
    async def literature(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP English Lit")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Language', style=nextcord.ButtonStyle.grey, custom_id='Language',
                       emoji='🗣️', row=1)
    async def language(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP English Lang")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Seminar', style=nextcord.ButtonStyle.grey, custom_id='Seminar',
                       emoji='💬', row=0)
    async def seminar(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Seminar")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Research', style=nextcord.ButtonStyle.grey, custom_id='Research',
                       emoji='🔍', row=1)
    async def research(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Research")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class Languages(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Japanese', style=nextcord.ButtonStyle.grey, custom_id='Japanese',
                       emoji='🗾', row=0)
    async def japanese(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Japanese")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Italian', style=nextcord.ButtonStyle.grey, custom_id='Italian',
                       emoji='🇮🇹', row=0)
    async def italian(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Italian")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Chinese', style=nextcord.ButtonStyle.grey, custom_id='Chinese',
                       emoji='🇨🇳', row=0)
    async def chinese(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Chinese")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Latin', style=nextcord.ButtonStyle.grey, custom_id='Latin',
                       emoji='🏛️', row=1)
    async def latin(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Latin")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='German', style=nextcord.ButtonStyle.grey, custom_id='German',
                       emoji='🇩🇪', row=1)
    async def german(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP German")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='French', style=nextcord.ButtonStyle.grey, custom_id='French',
                       emoji='🇫🇷', row=1)
    async def french(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP French")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Spanish Lang', style=nextcord.ButtonStyle.grey, custom_id='Spanish Lang',
                       emoji='🇪🇸', row=2)
    async def spanish_lang(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Spanish Lang")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Spanish Lit', style=nextcord.ButtonStyle.grey, custom_id='Spanish Lit',
                       emoji='📚', row=2)
    async def spanish_lit(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Spanish Lit")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class MathCS(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Precalc', style=nextcord.ButtonStyle.grey, custom_id='Precalc',
                       emoji='🧮', row=0)
    async def precalc(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Precalculus")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Calc AB', style=nextcord.ButtonStyle.grey, custom_id='Calc AB',
                       emoji='📘', row=1)
    async def calcab(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Calc AB")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Calc BC', style=nextcord.ButtonStyle.grey, custom_id='Calc BC',
                       emoji='📗', row=2)
    async def calcbc(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Calc BC")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Stats', style=nextcord.ButtonStyle.grey, custom_id='Stats',
                       emoji='📊', row=0)
    async def stats(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Stats")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Comp Sci A', style=nextcord.ButtonStyle.grey, custom_id='Comp Sci A',
                       emoji='💻', row=1)
    async def compscia(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP CompSci A")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Comp Sci Prin', style=nextcord.ButtonStyle.grey, custom_id='Comp Sci Prin',
                       emoji='🖥️', row=2)
    async def compsciprin(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP CompSci Prin")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Cybersecurity', style=nextcord.ButtonStyle.grey, custom_id='Cybersecurity',
                       emoji='🔐', row=3)
    async def cybersecurity(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Cybersecurity")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class Sciences(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Physics 1', style=nextcord.ButtonStyle.grey, custom_id='Physics 1',
                       emoji='⚛️', row=0)
    async def physics1(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Physics 1")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Physics 2', style=nextcord.ButtonStyle.grey, custom_id='Physics 2',
                       emoji='⚡', row=1)
    async def physics2(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Physics 2")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Chemistry', style=nextcord.ButtonStyle.grey, custom_id='Chemistry',
                       emoji='🧪', row=2)
    async def chemistry(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Chem")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Mech', style=nextcord.ButtonStyle.grey, custom_id='Mech',
                       emoji='⚙️', row=0)
    async def mech(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Physics C Mech")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='E/M', style=nextcord.ButtonStyle.grey, custom_id='E/M',
                       emoji='🧲', row=1)
    async def em(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Physics C E/M")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Enviro', style=nextcord.ButtonStyle.grey, custom_id='Enviro',
                       emoji='🌱', row=0)
    async def enviro(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Environ Sci")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Biology', style=nextcord.ButtonStyle.grey, custom_id='Biology',
                       emoji='🧬', row=1)
    async def biology(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Biology")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class SocialStudies(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Comp Gov', style=nextcord.ButtonStyle.grey, custom_id='Comp Gov',
                       emoji='🏛️', row=0)
    async def compgov(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Comparative Government")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='World M', style=nextcord.ButtonStyle.grey, custom_id='World M',
                       emoji='🌍', row=0)
    async def worldm(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP World History: Modern")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Human Geo', style=nextcord.ButtonStyle.grey, custom_id='Human Geo',
                       emoji='🗺️', row=1)
    async def humangeo(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Human Geo")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='US Gov', style=nextcord.ButtonStyle.grey, custom_id='US Gov',
                       emoji='🇺🇸', row=0)
    async def usgov(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP US Gov")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='APUSH', style=nextcord.ButtonStyle.grey, custom_id='APUSH',
                       emoji='🏛️', row=1)
    async def apush(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP US History")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Micro', style=nextcord.ButtonStyle.grey, custom_id='Micro',
                       emoji='📉', row=1)
    async def micro(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Micro")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Psych', style=nextcord.ButtonStyle.grey, custom_id='Psych',
                       emoji='🧠', row=0)
    async def psych(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Psych")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Euro', style=nextcord.ButtonStyle.grey, custom_id='Euro',
                       emoji='🇪🇺', row=1)
    async def euro(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Euro")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Macro', style=nextcord.ButtonStyle.grey, custom_id='Macro',
                       emoji='📈', row=2)
    async def macro(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Macro")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Business PF', style=nextcord.ButtonStyle.grey, custom_id='Business PF',
                       emoji='💼', row=2)
    async def businesspf(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="AP Business with Personal Finance")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class PostAP(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Post-AP Math', style=nextcord.ButtonStyle.grey, custom_id='Post-AP Math',
                       emoji='🧮', row = 0)
    async def postapmath(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Post-AP Math")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Higher Bio', style=nextcord.ButtonStyle.grey, custom_id='Higher Bio',
                       emoji='🧬', row = 0)
    async def higherbio(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Higher Bio")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


    @nextcord.ui.button(label='Higher CS', style=nextcord.ButtonStyle.grey, custom_id='Higher CS',
                       emoji='💻', row = 1)
    async def highercs(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Higher CS")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Higher Physics', style=nextcord.ButtonStyle.grey, custom_id='Higher Physics',
                       emoji='⚛️', row = 1)
    async def higherphysics(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Higher Physics")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


    @nextcord.ui.button(label='Higher Chem', style=nextcord.ButtonStyle.grey, custom_id='Higher Chem',
                       emoji='⚗️', row = 2)
    async def higherchem(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Higher Chem")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class Pronouns(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='she/her', style=nextcord.ButtonStyle.grey, custom_id='she',
                       emoji='♀️', row=0)
    async def she(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="she/her/hers")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='he/him', style=nextcord.ButtonStyle.grey, custom_id='he',
                       emoji='♂️', row=1)
    async def he(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="he/him/his")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='they/them', style=nextcord.ButtonStyle.grey, custom_id='they',
                       emoji='⚧️', row=0)
    async def they(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="they/them/theirs")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Ask me!', style=nextcord.ButtonStyle.grey, custom_id='ask',
                       emoji='❓', row=1)
    async def ask(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Ask me for my pronouns!")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class Booster(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='nitro-a', style=nextcord.ButtonStyle.grey, custom_id='A', row=0)
    async def nitroa(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="nitro-a")
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

    @nextcord.ui.button(label='nitro-b', style=nextcord.ButtonStyle.grey, custom_id='b', row=1)
    async def nitrob(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="nitro-b")
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

    @nextcord.ui.button(label='nitro-c', style=nextcord.ButtonStyle.grey, custom_id='C', row=2)
    async def nitroc(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="nitro-c")
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

    @nextcord.ui.button(label='nitro-d', style=nextcord.ButtonStyle.grey, custom_id='D', row=0)
    async def nitrod(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="nitro-d")
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

    @nextcord.ui.button(label='nitro-e', style=nextcord.ButtonStyle.grey, custom_id='E', row=1)
    async def nitroe(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="nitro-e")
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

    @nextcord.ui.button(label='nitro-f', style=nextcord.ButtonStyle.grey, custom_id='F', row=2)
    async def nitrof(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="nitro-f")
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


class LoungeOne(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Anime-Manga', style=nextcord.ButtonStyle.grey, custom_id='anime-manga',
                       emoji='🍡', row=0)
    async def animemanga(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Anime & Manga")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Art', style=nextcord.ButtonStyle.grey, custom_id='art',
                       emoji='🖌', row=1)
    async def art(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Art")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Books-Writing', style=nextcord.ButtonStyle.grey, custom_id='books-writing',
                       emoji='📚', row=2)
    async def bookswriting(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Books & Writing")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Events', style=nextcord.ButtonStyle.grey, custom_id='events',
                       emoji='🎉', row=0)
    async def events(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Events")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Fashion', style=nextcord.ButtonStyle.grey, custom_id='fashion',
                       emoji='👓', row=1)
    async def fashion(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Fashion")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Film-TV', style=nextcord.ButtonStyle.grey, custom_id='film-tv',
                       emoji='🎬', row=2)
    async def filmtv(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Film & TV")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class LoungeTwo(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Food', style=nextcord.ButtonStyle.grey, custom_id='food',
                       emoji='🍔', row=0)
    async def food(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Food")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Gaming', style=nextcord.ButtonStyle.grey, custom_id='gaming',
                       emoji='🎮', row=1)
    async def gaming(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Gaming")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Languages', style=nextcord.ButtonStyle.grey, custom_id='languages',
                       emoji='🌐', row=2)
    async def languages(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Languages")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Music', style=nextcord.ButtonStyle.grey, custom_id='music',
                       emoji='🎵', row=0)
    async def music(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Music")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Pets', style=nextcord.ButtonStyle.grey, custom_id='pets',
                       emoji='🐶', row=1)
    async def pets(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Pets")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Photography', style=nextcord.ButtonStyle.grey, custom_id='photography',
                       emoji='📷', row=2)
    async def photography(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Photography")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)


class LoungeThree(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @nextcord.ui.button(label='Sports', style=nextcord.ButtonStyle.grey, custom_id='sports',
                       emoji='⚽', row=0)
    async def sports(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Sports")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Tech', style=nextcord.ButtonStyle.grey, custom_id='tech',
                       emoji='💻', row=0)
    async def tech(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Tech")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Wordle', style=nextcord.ButtonStyle.grey, custom_id='wordle',
                       emoji='🟩', row=1)
    async def wordle(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Wordle")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label='Opt-Out of Lounge', style=nextcord.ButtonStyle.red, custom_id='languages', row=1)
    async def optout(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        role = nextcord.utils.get(interaction.guild.roles, name="Lounge: Opt-Out")
        member = interaction.guild.get_member(interaction.user.id)

        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

class Region(nextcord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    REGION_ROLES = [
        "Region: North America",
        "Region: South America",
        "Region: Europe",
        "Region: Africa",
        "Region: Asia",
        "Region: Oceania",
        "Region: Prefer Not to Say",
    ]

    async def toggle_region(self, interaction: nextcord.Interaction, role_name: str):
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message("Member not found in this guild.", ephemeral=True)
            return

        role = nextcord.utils.get(interaction.guild.roles, name=role_name)
        if role is None:
            await interaction.response.send_message(f"`{role_name}` role not found.", ephemeral=True)
            return

        # If they already have it, remove it
        if role in member.roles:
            await member.remove_roles(role)
            await interaction.response.send_message(f"`{role.name}` role removed!", ephemeral=True)
            return

        # Remove any other region role first, so they only have one
        for region_role_name in self.REGION_ROLES:
            region_role = nextcord.utils.get(interaction.guild.roles, name=region_role_name)
            if region_role and region_role in member.roles:
                await member.remove_roles(region_role)

        await member.add_roles(role)
        await interaction.response.send_message(f"`{role.name}` role added!", ephemeral=True)

    @nextcord.ui.button(label="North America", style=nextcord.ButtonStyle.grey, custom_id="region_north_america", emoji="🌎", row=0)
    async def north_america(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.toggle_region(interaction, "Region: North America")

    @nextcord.ui.button(label="South America", style=nextcord.ButtonStyle.grey, custom_id="region_south_america", emoji="🌎", row=0)
    async def south_america(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.toggle_region(interaction, "Region: South America")

    @nextcord.ui.button(label="Europe", style=nextcord.ButtonStyle.grey, custom_id="region_europe", emoji="🌍", row=0)
    async def europe(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.toggle_region(interaction, "Region: Europe")

    @nextcord.ui.button(label="Africa", style=nextcord.ButtonStyle.grey, custom_id="region_africa", emoji="🌍", row=1)
    async def africa(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.toggle_region(interaction, "Region: Africa")

    @nextcord.ui.button(label="Asia", style=nextcord.ButtonStyle.grey, custom_id="region_asia", emoji="🌏", row=1)
    async def asia(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.toggle_region(interaction, "Region: Asia")

    @nextcord.ui.button(label="Oceania", style=nextcord.ButtonStyle.grey, custom_id="region_oceania", emoji="🌊", row=1)
    async def oceania(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.toggle_region(interaction, "Region: Oceania")

    @nextcord.ui.button(label="Prefer Not to Say", style=nextcord.ButtonStyle.grey, custom_id="region_prefer_not_to_say", emoji="❔", row=2)
    async def prefer_not_to_say(self, button: nextcord.ui.Button, interaction: nextcord.Interaction):
        await self.toggle_region(interaction, "Region: Prefer Not to Say")


class RoleReact(commands.Cog):
    """Role React (3 commands only)"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _post_panel(self, interaction: Interaction, title: str, description: str,
                          color: nextcord.Color, image_url: str, view: nextcord.ui.View):
        embed = nextcord.Embed(title=title, description=description, color=color)
        if image_url:
            embed.set_image(url=image_url)
        await interaction.followup.send(embed=embed, view=view)

    @slash_command(name="rolesignup", description="Post all AP role signup panels", guild_ids=[conf.get("guild_id")])
    @application_checks.has_any_role(*ALLOWED_ROLES)
    async def rolesignup(self, interaction: Interaction):
        # ✅ no message, just acknowledge silently
        await interaction.response.defer()

        common_desc = (
            "To access subject channels for specific AP classes, click on a button to receive the role.\n"
            "To remove the role, click on the button again."
        )

        await self._post_panel(interaction, "Welcome to the server!", common_desc, nextcord.Color.orange(),
            "https://media.discordapp.net/attachments/787749899160387674/1061800484832301066/arts.png?ex=686bba82&is=686a6902&hm=d7e0efa54909fdb3eed15b0bf0e66fa5cc04df870d899dd1b0e25ca42db7e123&=&width=1242&height=767",
            Arts(self.bot))

        await self._post_panel(interaction, "Welcome to the server!", common_desc, nextcord.Color.from_rgb(100, 149, 237),
            "https://media.discordapp.net/attachments/787749899160387674/1061800485184602112/English.png?ex=686bba82&is=686a6902&hm=f1c3e0caeb46373881badb476d793197dfedd9c5bf1816ddcda0e70da4828291&=&width=1439&height=890",
            English(self.bot))

        await self._post_panel(interaction, "Welcome to the server!", common_desc, nextcord.Color.from_rgb(255, 165, 0),
            "https://media.discordapp.net/attachments/787749899160387674/1061800485515968542/Languages.png?ex=686bba83&is=686a6903&hm=42d835b7d73cc748663490276bde5ce5600397db4245eb78943adb33341ec9e5&=&width=1439&height=890",
            Languages(self.bot))

        await self._post_panel(interaction, "Welcome to the server!", common_desc, nextcord.Color.from_rgb(72, 209, 204),
            "https://cdn.discordapp.com/attachments/791130847461507093/1541614961111867424/content.png?ex=6a8e3c50&is=6a8cead0&hm=0d1a2e54a4d8a099b2fa8a773ef5d6cb2f5d302c1ec3f347bf34451ff8185f2e&",
            MathCS(self.bot))

        await self._post_panel(interaction, "Welcome to the server!", common_desc, nextcord.Color.from_rgb(144, 238, 144),
            "https://media.discordapp.net/attachments/518668543437570061/599914180828594206/bruh_moment.png?ex=686ba51e&is=686a539e&hm=b1740201dbc2d4a23ded595eb552090b7dcdc6380f6d8d3ee79ea3b6e8f84238&=&width=1439&height=890",
            Sciences(self.bot))

        await self._post_panel(interaction, "Welcome to the server!", common_desc, nextcord.Color.from_rgb(255, 215, 0),
            "https://cdn.discordapp.com/attachments/791130847461507093/1541616060896387082/content.png?ex=6a8e3d56&is=6a8cebd6&hm=4c068e7fbc513e17ee3876bab49278e3efec66894b611656fcd8be2c26d72120&",
            SocialStudies(self.bot))

        await self._post_panel(interaction, "Welcome to the server!", common_desc, nextcord.Color.from_rgb(186, 85, 211),
            "https://cdn.discordapp.com/attachments/791130847461507096/1470030943048831168/image.png?ex=6989d080&is=69887f00&hm=4d0d5b3611e24cbc797bc58e591acfc294b26f20ef43244b01857ab7c06fea7f",
            PostAP(self.bot))

    @slash_command(name="nitro-perks", description="Post Nitro Booster perks panel", guild_ids=[conf.get("guild_id")])
    @application_checks.has_any_role(*ALLOWED_ROLES)
    async def nitro_perks(self, interaction: Interaction):
        await interaction.response.defer()

        embed = nextcord.Embed(
            title="Thanks for boosting the server!",
            description=(
                "As special thanks, if you’d like you can pick a new role color from the following colors—"
                "note that the color will last for the duration of the boost."
            ),
            color=nextcord.Color.teal()
        )
        embed.set_image(
            url="https://cdn.discordapp.com/attachments/791130847461507093/1391460319892733962/image.png?ex=686bf9e8&is=686aa868&hm=8a55fcc3b4a5ec4dfef2b46635c760003d7a618070751a943a467a687a1726ac&"
        )
        await interaction.followup.send(embed=embed, view=Booster(self.bot), ephemeral=False)

    @slash_command(name="lougue-signup", description="Post Lounge role signup panels", guild_ids=[conf.get("guild_id")])
    @application_checks.has_any_role(*ALLOWED_ROLES)
    async def lougue_signup(self, interaction: Interaction):
        await interaction.response.defer()

        desc = "Welcome to Lounge! Sign up for roles to talk about non-academic subjects! Note that the events role will ping you everytime there's an event."

        await self._post_panel(interaction, "Choose Your Lounge One Roles", desc, nextcord.Color.teal(),
            "https://media.discordapp.net/attachments/787749899160387674/1066274148067840140/Lounge_1.png?ex=686b862f&is=686a34af&hm=725d4acc9e5d574735c268e1708a539f4de09f2d7f5f8e6dcd0f933610679629&=&width=1439&height=890",
            LoungeOne(self.bot))

        await self._post_panel(interaction, "Choose Your Lounge Two Roles", desc, nextcord.Color.teal(),
            "https://media.discordapp.net/attachments/787749899160387674/1066274148319502417/Lounge_2.png?ex=686b862f&is=686a34af&hm=3762982f62b69009e2b0b7e5aad8041c864b856c0d8278efc8d50f724c7d5da1&=&width=1439&height=890",
            LoungeTwo(self.bot))

        await self._post_panel(interaction, "Choose Your Lounge Three Roles", desc, nextcord.Color.teal(),
            "https://media.discordapp.net/attachments/791130847461507093/1391476764072611962/image.png?ex=686c0938&is=686ab7b8&hm=1b2ee60ac99963457ce7888d2680298cefef72616c79090f130b8bc9ebc8969b&=&width=1458&height=868",
            LoungeThree(self.bot))

    @slash_command(name="region-signup", description="Post region role signup panel", guild_ids=[conf.get("guild_id")])
    @application_checks.has_any_role(*ALLOWED_ROLES)
    async def region_signup(self, interaction: Interaction):
        await interaction.response.defer()

        desc = (
            "Select the region/continent that best describes where you are from.\n"
            "Click again to remove the role. Choosing a new region will replace your old region role."
        )

        await self._post_panel(
            interaction,
            "Choose Your Region",
            desc,
            nextcord.Color.teal(),
            "https://cdn.discordapp.com/attachments/791130847461507093/1513701561061347459/image.png?ex=6a28afef&is=6a275e6f&hm=f39e5e6f0b96ed98a22e6bcc52a333bf9956e79930a8cfaae20f3f3e9a77d8dd&",
            Region(self.bot)
        )




def setup(bot):
    bot.add_cog(RoleReact(bot))


    bot.add_view(Arts(bot))
    bot.add_view(English(bot))
    bot.add_view(Languages(bot))
    bot.add_view(MathCS(bot))
    bot.add_view(Sciences(bot))
    bot.add_view(SocialStudies(bot))
    bot.add_view(PostAP(bot))

    bot.add_view(Booster(bot))

    bot.add_view(LoungeOne(bot))
    bot.add_view(LoungeTwo(bot))
    bot.add_view(LoungeThree(bot))

    bot.add_view(Region(bot))
