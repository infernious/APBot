import motor
import io
import discord
from discord.ext import commands
from discord import app_commands

ROLE_CAN_MAKE_MACROS = ["Chat Moderator", "Admin", "Honorable"]

FAILURE_EMBED = discord.Embed(colour=discord.Colour.red())
SUCCESS_EMBED = discord.Embed(colour=discord.Colour.green())

ALLOWED_MENTIONS = discord.AllowedMentions.none()
ALLOWED_MENTIONS.replied_user = True

DISCORD_FILE_LIMIT = 10

class File:
    """
    A file to store in the macro db
    """

    def __init__(self, filename: str, data: bytes):

        self.filename = filename
        self.data = data

class MacroDb:
    """
    Manages access to macro storage
    """

    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorCollection):

        self.db = db

    async def get_macro(self, name: str) -> str | None:
    
        maybe_found = await self.db.find_one({"name": name})
        if not maybe_found:
            return None

        return maybe_found

    async def insert_macro(self, name: str, value: str, attachments: list[File] | None) -> None:

        if not attachments:
            attachments = []
        
        attachments = [{"filename": attachment.filename, "data": attachment.data} for attachment in attachments]

        if await self.get_macro(name):
            raise KeyError("Macro already exists - try removing it first?")

        # Security: no idc about sanitization because mods are nice right guys?
        # Okay maybe I do care but I'll just remember to remove mentions from the bot when using macros
        await self.db.insert_one({"name": name, "value": value, "attachments": attachments[:DISCORD_FILE_LIMIT]})

    async def delete_macro(self, name: str) -> None:

        if not await self.get_macro(name):
            raise KeyError("Macro doesn't exist - can't be deleted")
        
        macro = await self.db.delete_one({"name": name})

    async def list_macros(self) -> list[str]:

        macros = await self.db.find({"name": {"$exists": True}}).to_list(length=None)
        return list(map(lambda macro: macro["name"], macros))


class MacroNameTextbox(discord.ui.Modal):
    """
    A text box to let a user chose a macro name
    """

    macro_name = discord.ui.TextInput(label="Type macro name here", placeholder="macro name")

    def __init__(self, macro_content: discord.Message, macro_db: MacroDb):

        super().__init__(title="Macro Name")
        self.macro_content = macro_content
        self.macro_db = macro_db

    async def on_submit(self, interaction: discord.Interaction): 

        # TODO: beg python devs for async-await in lambdas and/or list comprehension
        new_attachments = []
        for attachment in self.macro_content.attachments:
            new_attachments.append(File(attachment.filename, await attachment.read()))

        try:
            await self.macro_db.insert_macro(str(self.macro_name), self.macro_content.content, attachments=new_attachments)

            embed = SUCCESS_EMBED
            embed.title = "Success"
            embed.description = f"Macro `{self.macro_name}` is available!"
            
        except KeyError as e:
            embed = FAILURE_EMBED
            embed.title = "Failed to create macro"
            embed.description = f"{e}"
            
        await interaction.response.send_message(embed=embed)


def can_make_macros(interaction: discord.Interaction) -> bool:

    check = any([role.name in ROLE_CAN_MAKE_MACROS for role in interaction.user.roles])
    if not check:
        raise commands.CommandError(message=f"No permission to create macros! Needs to have one of these roles: {ROLE_CAN_MAKE_MACROS}")
    return check


class Macros(commands.Cog):
    """
    A system to let users respond with automated replies.
    Because getting asked for study resources all the time is annoying :(
    """

    async def new_macro(self, interaction: discord.Interaction, message: discord.Message):
        """
        Creates a new macro that any user can use.
        """

        await interaction.response.send_modal(MacroNameTextbox(message, self.macro_db))

    def __init__(self, bot: commands.Bot, macro_db: MacroDb):
    
        self.bot = bot
        self.macro_db = macro_db

        new_macro_menu = app_commands.ContextMenu(name='New Macro', callback=self.new_macro)
        new_macro_menu.add_check(can_make_macros)
        self.bot.tree.add_command(new_macro_menu)

    @app_commands.command(name='macro', description="Uses a macro, replying to the user with the macro contents.")
    async def use_macro(self, interaction: discord.Interaction, macro_name: str):
        """
        Uses a macro, replying to the user with the macro contents.
        """

        await interaction.response.defer()

        maybe_macro = await self.macro_db.get_macro(macro_name)
        if maybe_macro:
            files = [discord.File(io.BytesIO(file["data"]), filename=file["filename"]) for file in maybe_macro["attachments"]]
            await interaction.followup.send(maybe_macro["value"], files=files, allowed_mentions=ALLOWED_MENTIONS)
        else:
            embed = FAILURE_EMBED
            embed.title = "Macro bytesbytesnot found"
            await interaction.followup.send(embed=embed)

    @app_commands.check(can_make_macros)
    @app_commands.command(name='remove_macro', description="Removes a macro, preventing it from being used.")
    async def remove_macro(self, interaction: discord.Interaction, macro_name: str):
        """
        Removes a macro, preventing it from being used.
        """

        await interaction.response.defer()

        try:
            await self.macro_db.delete_macro(macro_name)

            embed = FAILURE_EMBED
            embed.title = "Success"
            embed.description = f"Macro `{macro_name}` has been deleted."
            
        except KeyError as e:
            embed = FAILURE_EMBED
            embed.title = "Failed to delete macro"
            embed.description = f"{e}"

        await interaction.followup.send(embed=embed)

    @app_commands.command(name='listmacros', description="Lists all active macros")
    async def list_macros(self, interaction: discord.Interaction):
        """
        Lists all active macros
        """

        await interaction.response.defer()

        await interaction.followup.send(embed=discord.Embed(title="Available macros", description=", ".join(await self.macro_db.list_macros())))

async def setup(bot: commands.Bot) -> None:
    macro_db = MacroDb(bot.macros)
    await bot.add_cog(Macros(bot, macro_db), guilds=[discord.Object(id=bot.guild_id)])
    await bot.tree.sync() # Necessary to make our manually added (no decorator) commands show
