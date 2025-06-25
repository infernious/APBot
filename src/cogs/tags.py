import re
from nextcord import Embed, Interaction, SlashOption, slash_command, Attachment
from nextcord.ext import commands
from bot_base import APBot  # Ensure this is imported correctly

class Tags(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="tag", description="Manage tags")
    async def _tag(self, inter: Interaction):
        pass  # Main command logic, if needed.

    @_tag.subcommand(name="create", description="Create a new tag")
    async def _tag_create(
        self,
        inter: Interaction,
        name: str = SlashOption("name", description="Name of the tag", required=True),
        content: Attachment = SlashOption("content", description="Content of the tag as a file or image", required=True)
    ) -> None:
        # Handle the content as a file or image
        content_url = content.url  # Get the URL of the uploaded attachment
        # Check if the tag already exists
        if await self.bot.db.tags.exists(inter.guild.id, name):
            return await inter.send("A tag with this name already exists.", ephemeral=False)

        # Create the tag in the database
        await self.bot.db.tags.create(inter.guild.id, inter.user.id, name, content_url)
        await inter.send(f"Tag '{name}' created successfully!", ephemeral=False)

    @_tag.subcommand(name="delete", description="Delete an existing tag")
    async def _tag_delete(
        self,
        inter: Interaction,
        name: str = SlashOption("name", description="Name of the tag", required=True)
    ) -> None:
        # Check if the tag exists
        if not await self.bot.db.tags.exists(inter.guild.id, name):
            return await inter.send("Tag not found.", ephemeral=False)

        # Delete the tag from the database
        await self.bot.db.tags.delete(inter.guild.id, name)
        await inter.send(f"Tag '{name}' deleted successfully!", ephemeral=False)

    @_tag.subcommand(name="list", description="List all tags")
    async def _tag_list(self, inter: Interaction) -> None:
        # Fetch all tags for the guild
        tags = await self.bot.db.tags.get_all(inter.guild.id)

        if not tags:
            return await inter.send("No tags available in this server.", ephemeral=False)

        # Format the list of tags
        tag_list = "\n".join(f"- {tag['name']}" for tag in tags)
        await inter.send(embed=Embed(title="Available Tags", description=tag_list), ephemeral=False)

    @_tag.subcommand(name="edit", description="Edit an existing tag")
    async def _tag_edit(
        self,
        inter: Interaction,
        name: str = SlashOption("name", description="Name of the tag", required=True),
        new_content: str = SlashOption("new_content", description="New content for the tag", required=True)
    ) -> None:
        # Check if the tag exists
        if not await self.bot.db.tags.exists(inter.guild.id, name):
            return await inter.send("Tag not found.", ephemeral=False)

        # Update the tag content in the database
        await self.bot.db.tags.update(inter.guild.id, name, new_content)
        await inter.send(f"Tag '{name}' updated successfully!", ephemeral=False)

    @_tag.subcommand(name="display", description="Display a tag's content")
    async def _tag_display(
        self,
        inter: Interaction,
        name: str = SlashOption("name", description="Name of the tag", required=True)
    ) -> None:
        # Fetch the tag content
        tag = await self.bot.db.tags.get_tag(inter.guild.id, name)
        if not tag:
            return await inter.send("Tag not found.", ephemeral=False)

        # Extract content
        tag_content = tag['content']
        
        # Regular expression to find URLs in the content
        url_pattern = r"(https?://[^\s]+)"
        urls = re.findall(url_pattern, tag_content)

        # Remove URLs from content for display
        text_content = re.sub(url_pattern, "", tag_content).strip()

        # Send message with image
        if urls:
            # Send the text content first
            if text_content:
                await inter.send(f"Tag '{name}' content:\n{text_content}", ephemeral=False)

            # Send the image
            for url in urls:
                await inter.send(url, ephemeral=False)
        else:
            # Send text content only if no image URLs found
            await inter.send(f"Tag '{name}' content:\n{text_content}", ephemeral=False)

    @commands.Cog.listener("on_ready")
    async def _tag_on_ready(self) -> None:
        print("Tag cog is ready.")

def setup(bot: APBot):
    bot.add_cog(Tags(bot))

