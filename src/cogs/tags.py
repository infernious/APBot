import re
from nextcord import Embed, Interaction, SlashOption, slash_command, Attachment
from nextcord.ext import commands
from bot_base import APBot  # Ensure this is imported correctly

# Only these roles can run the commands
REQUIRED_ROLES = {"Honorable", "Chat Moderator", "Admin"}

class Tags(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    def _has_required_role(self, inter: Interaction) -> bool:
        """Check if the user has at least one of the required roles."""
        return any(role.name in REQUIRED_ROLES for role in inter.user.roles)

    @slash_command(name="tag", description="Manage tags")
    async def _tag(self, inter: Interaction):
        pass  # Root command

    @_tag.subcommand(name="create", description="Create a new tag")
    async def _tag_create(
        self,
        inter: Interaction,
        name: str = SlashOption("name", description="Name of the tag", required=True),
        content: Attachment = SlashOption("content", description="Content of the tag as a file or image", required=True)
    ) -> None:
        if not self._has_required_role(inter):
            return await inter.send("You don't have permission to use this command.", ephemeral=True)

        content_url = content.url
        if await self.bot.db.tags.exists(inter.guild.id, name):
            return await inter.send("A tag with this name already exists.", ephemeral=True)

        await self.bot.db.tags.create(inter.guild.id, inter.user.id, name, content_url)
        await inter.send(f"Tag '{name}' created successfully!", ephemeral=False)

    @_tag.subcommand(name="delete", description="Delete an existing tag")
    async def _tag_delete(
        self,
        inter: Interaction,
        name: str = SlashOption("name", description="Name of the tag", required=True)
    ) -> None:
        if not self._has_required_role(inter):
            return await inter.send("You don't have permission to use this command.", ephemeral=True)

        if not await self.bot.db.tags.exists(inter.guild.id, name):
            return await inter.send("Tag not found.", ephemeral=True)

        await self.bot.db.tags.delete(inter.guild.id, name)
        await inter.send(f"Tag '{name}' deleted successfully!", ephemeral=False)

    @_tag.subcommand(name="list", description="List all tags")
    async def _tag_list(self, inter: Interaction) -> None:
        if not self._has_required_role(inter):
            return await inter.send("You don't have permission to use this command.", ephemeral=True)

        tags = await self.bot.db.tags.get_all(inter.guild.id)
        if not tags:
            return await inter.send("No tags available in this server.", ephemeral=False)

        tag_list = "\n".join(f"- {tag['name']}" for tag in tags)
        await inter.send(embed=Embed(title="Available Tags", description=tag_list), ephemeral=False)

    @_tag.subcommand(name="display", description="Display a tag's content")
    async def _tag_display(
        self,
        inter: Interaction,
        name: str = SlashOption("name", description="Name of the tag", required=True)
    ) -> None:
        if not self._has_required_role(inter):
            return await inter.send("You don't have permission to use this command.", ephemeral=True)

        tag = await self.bot.db.tags.get_tag(inter.guild.id, name)
        if not tag:
            return await inter.send("Tag not found.", ephemeral=False)

        tag_content = tag['content']
        url_pattern = r"(https?://[^\s]+)"
        urls = re.findall(url_pattern, tag_content)
        text_content = re.sub(url_pattern, "", tag_content).strip()

        if urls:
            if text_content:
                await inter.send(f"Tag '{name}' content:\n{text_content}", ephemeral=False)
            for url in urls:
                await inter.send(url, ephemeral=False)
        else:
            await inter.send(f"Tag '{name}' content:\n{text_content}", ephemeral=False)

    @commands.Cog.listener("on_ready")
    async def _tag_on_ready(self) -> None:
        print("Tag cog is ready.")

def setup(bot: APBot):
    bot.add_cog(Tags(bot))
