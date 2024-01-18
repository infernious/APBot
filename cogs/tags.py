import motor
import io
import nextcord
from nextcord.ext import commands
from nextcord import app_commands

ROLE_CAN_MAKE_TAGS = ["Chat Moderator", "Admin", "Honorable"]

FAILURE_EMBED = nextcord.Embed(colour=nextcord.Colour.red())
SUCCESS_EMBED = nextcord.Embed(colour=nextcord.Colour.green())

ALLOWED_MENTIONS = nextcord.AllowedMentions.none()
ALLOWED_MENTIONS.replied_user = True

DISCORD_FILE_LIMIT = 10

class File:
    """
    A file to store in the tag db
    """

    def __init__(self, filename: str, data: bytes):

        self.filename = filename
        self.data = data

class TagDb:
    """
    Manages access to tag storage
    """

    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorCollection):

        self.db = db

    async def get_tag(self, name: str) -> str | None:
    
        maybe_found = await self.db.find_one({"name": name})
        if not maybe_found:
            return None

        return maybe_found

    async def insert_tagself, name: str, value: str, attachments: list[File] | None) -> None:

        if not attachments:
            attachments = []
        
        attachments = [{"filename": attachment.filename, "data": attachment.data} for attachment in attachments]

        if await self.get_tag(name):
            raise KeyError("Tag already exists - try removing it first?")

        # Security: no idc about sanitization because mods are nice right guys?
        # Okay maybe I do care but I'll just remember to remove mentions from the bot when using tags
        await self.db.insert_one({"name": name, "value": value, "attachments": attachments[:DISCORD_FILE_LIMIT]})

    async def delete_tag(self, name: str) -> None:

        if not await self.get_tag(name):
            raise KeyError("Tag doesn't exist - can't be deleted")
        
        tag = await self.db.delete_one({"name": name})

    async def list_tags(self) -> list[str]:

        tags = await self.db.find({"name": {"$exists": True}}).to_list(length=None)
        return list(map(lambda tag: tag["name"], tags))


class TagNameTextbox(nextcord.ui.Modal):
    """
    A text box to let a user chose a tag name
    """

    tag_name = nextcord.ui.TextInput(label="Type tag name here", placeholder="tag name")

    def __init__(self, tag_content: nextcord.Message, tag_db: TagDb):

        super().__init__(title="Tag Name")
        self.tag_content = tag_content
        self.tag_db = tag_db

    async def on_submit(self, interaction: nextcord.Interaction): 

        # TODO: beg python devs for async-await in lambdas and/or list comprehension
        new_attachments = []
        for attachment in self.tag_content.attachments:
            new_attachments.append(File(attachment.filename, await attachment.read()))

        try:
            await self.tag_db.insert_tag(str(self.tag_name), self.tag_content.content, attachments=new_attachments)

            embed = SUCCESS_EMBED
            embed.title = "Success"
            embed.description = f"Tag `{self.tag_name}` is available!"
            
        except KeyError as e:
            embed = FAILURE_EMBED
            embed.title = "Failed to create tag"
            embed.description = f"{e}"
            
        await interaction.response.send_message(embed=embed)


def can_make_tags(interaction: nextcord.Interaction) -> bool:

    check = any([role.name in ROLE_CAN_MAKE_TAGS for role in interaction.user.roles])
    if not check:
        raise commands.CommandError(message=f"No permission to create tags! Needs to have one of these roles: {ROLE_CAN_MAKE_TAGS}")
    return check


class Tags(commands.Cog):
    """
    A system to let users respond with automated replies.
    Because getting asked for study resources all the time is annoying :(
    """

    async def new_tag(self, interaction: nextcord.Interaction, message: nextcord.Message):
        """
        Creates a new tag that any user can use.
        """

        await interaction.response.send_modal(TagNameTextbox(message, self.tag_db))

    def __init__(self, bot: commands.Bot, tag_db: TagDb):
    
        self.bot = bot
        self.tag_db = tag_db

        new_tag_menu = app_commands.ContextMenu(name='New Tag', callback=self.new_tag)
        new_tag_menu.add_check(can_make_tags)
        self.bot.tree.add_command(new_tag_menu)

    @app_commands.command(name='tag', description="Uses a tag, replying to the user with the tag contents.")
    async def use_tag(self, interaction: nextcord.Interaction, tag_name: str):
        """
        Uses a tag, replying to the user with the tag contents.
        """

        await interaction.response.defer()

        maybe_tag = await self.tag_db.get_tag(tag_name)
        if maybe_tag:
            files = [nextcord.File(io.BytesIO(file["data"]), filename=file["filename"]) for file in maybe_tag["attachments"]]
            await interaction.followup.send(maybe_tag["value"], files=files, allowed_mentions=ALLOWED_MENTIONS)
        else:
            embed = FAILURE_EMBED
            embed.title = "Tag bytesbytesnot found"
            await interaction.followup.send(embed=embed)

    @app_commands.check(can_make_tags)
    @app_commands.command(name='remove_tag', description="Removes a tag, preventing it from being used.")
    async def remove_tag(self, interaction: nextcord.Interaction, tag_name: str):
        """
        Removes a tag, preventing it from being used.
        """

        await interaction.response.defer()

        try:
            await self.tag_db.delete_tag(tag_name)

            embed = FAILURE_EMBED
            embed.title = "Success"
            embed.description = f"Tag `{tag_name}` has been deleted."
            
        except KeyError as e:
            embed = FAILURE_EMBED
            embed.title = "Failed to delete tag"
            embed.description = f"{e}"

        await interaction.followup.send(embed=embed)

    @app_commands.command(name='listtags', description="Lists all active tags")
    async def list_tags(self, interaction: nextcord.Interaction):
        """
        Lists all active tags
        """

        await interaction.response.defer()

        await interaction.followup.send(embed=nextcord.Embed(title="Available tags", description=", ".join(await self.tag_db.list_tags())))

async def setup(bot: commands.Bot) -> None:
    tag_db = TagDb(bot.tags)
    await bot.add_cog(Tags(bot, tag_db), guilds=[nextcord.Object(id=bot.guild_id)])
    await bot.tree.sync() # Necessary to make our manually added (no decorator) commands show
