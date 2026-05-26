from nextcord import Attachment, Embed, Interaction, SlashOption, slash_command
from nextcord.ext import commands
from bot_base import APBot
from app_config import get_command_guild_ids, load_optional_config

conf = load_optional_config()
COMMAND_GUILD_IDS = get_command_guild_ids(conf)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def normalize_tag_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def has_role(member, role_name: str) -> bool:
    return any(getattr(role, "name", None) == role_name for role in getattr(member, "roles", []))


def can_upload_tag_image(member) -> bool:
    return has_role(member, "Honorable")


def is_image_attachment(attachment: Attachment) -> bool:
    content_type = getattr(attachment, "content_type", None)
    filename = getattr(attachment, "filename", "") or ""

    if content_type and content_type.startswith("image/"):
        return True

    return filename.lower().endswith(IMAGE_EXTENSIONS)


class Tags(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="tag", description="Manage private tags", guild_ids=COMMAND_GUILD_IDS)
    async def tag(self, inter: Interaction):
        pass

    @tag.subcommand(name="create", description="Create a private tag")
    async def tag_create(
        self,
        inter: Interaction,
        name: str = SlashOption(name="name", description="Name of the tag", required=True),
        content: str = SlashOption(name="content", description="Text content for the tag", required=True),
        image: Attachment = SlashOption(name="image", description="Optional image for Honorable users", required=False),
    ) -> None:
        tag_name = normalize_tag_name(name)

        if not tag_name:
            await inter.send("Tag name cannot be empty.", ephemeral=True)
            return

        if not content.strip():
            await inter.send("Tag content cannot be empty.", ephemeral=True)
            return

        image_url = None
        if image is not None:
            if not can_upload_tag_image(inter.user):
                await inter.send("Only members with the Honorable role can upload images with tags.", ephemeral=True)
                return

            if not is_image_attachment(image):
                await inter.send("Tag image must be an image file.", ephemeral=True)
                return

            image_url = image.url

        if await self.bot.db.tags.exists(inter.guild.id, inter.user.id, tag_name):
            await inter.send("You already have a tag with this name.", ephemeral=True)
            return

        await self.bot.db.tags.create(inter.guild.id, inter.user.id, tag_name, content.strip(), image_url)
        await inter.send(f"Tag `{tag_name}` created successfully.", ephemeral=True)

    @tag.subcommand(name="delete", description="Delete one of your private tags")
    async def tag_delete(
        self,
        inter: Interaction,
        name: str = SlashOption(name="name", description="Name of the tag", required=True),
    ) -> None:
        tag_name = normalize_tag_name(name)

        if not await self.bot.db.tags.exists(inter.guild.id, inter.user.id, tag_name):
            await inter.send("Tag not found.", ephemeral=True)
            return

        await self.bot.db.tags.delete(inter.guild.id, inter.user.id, tag_name)
        await inter.send(f"Tag `{tag_name}` deleted successfully.", ephemeral=True)

    @tag.subcommand(name="list", description="List your private tags")
    async def tag_list(self, inter: Interaction) -> None:
        tags = await self.bot.db.tags.get_all(inter.guild.id, inter.user.id)

        if not tags:
            await inter.send("You do not have any saved tags.", ephemeral=True)
            return

        tag_list = "\n".join(f"- {tag['name']}" for tag in tags)
        await inter.send(embed=Embed(title="Your Tags", description=tag_list), ephemeral=True)

    @tag.subcommand(name="display", description="Display one of your private tags")
    async def tag_display(
        self,
        inter: Interaction,
        name: str = SlashOption(name="name", description="Name of the tag", required=True),
    ) -> None:
        tag_name = normalize_tag_name(name)
        tag_data = await self.bot.db.tags.get_tag(inter.guild.id, inter.user.id, tag_name)

        if not tag_data:
            await inter.send("Tag not found.", ephemeral=True)
            return

        embed = Embed(title=tag_data["name"], description=tag_data.get("content") or "")
        if tag_data.get("image_url"):
            embed.set_image(url=tag_data["image_url"])

        await inter.send(embed=embed, ephemeral=False)

    @commands.Cog.listener("on_ready")
    async def tag_on_ready(self) -> None:
        print("Tag cog is ready.")


def setup(bot: APBot):
    bot.add_cog(Tags(bot))
