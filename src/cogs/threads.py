import asyncio
import nextcord
from nextcord import Interaction, Embed, Object, ui, Color
from nextcord.ext import commands
from nextcord import slash_command

blue = Color.teal()

""" Under work for later updates """
class PingHelpers(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Ping Helpers!", style=nextcord.ButtonStyle.red)
    async def ping_helpers(self, button: ui.Button, interaction: Interaction):
        """
        Confirm mention after command is used as to avoid accidental pings.
        - Currently uses subject tags to find the helper role
        """
        button.style = nextcord.ButtonStyle.green
        button.emoji = "✅"
        button.label = "Helpers pinged!"
        button.disabled = True
        self.dismiss.disabled = True

        await interaction.response.edit_message(view=self)

        helpers = []
        for tag in interaction.channel.applied_tags:
            role = nextcord.utils.get(interaction.guild.roles, name=f"{tag.name} Helper")
            if role:
                helpers.append(role)

        try:
            pins = await interaction.channel.pins()
            if helpers:
                await pins[0].reply(f"{helpers[0].mention}, a question has been asked!")
                self.stop()
            else:
                await interaction.followup.send("No helper roles found for the tag.", ephemeral=True)
        except Exception:
            await interaction.followup.send(
                "Please edit your post to have a subject tag first.", ephemeral=True
            )

    @ui.button(label="Dismiss", style=nextcord.ButtonStyle.grey, custom_id="dismiss_button")
    async def dismiss(self, button: ui.Button, interaction: Interaction):
        """
        Dismiss options to ping helpers.
        """
        await interaction.message.delete()
        await interaction.response.send_message(
            "Please add the `✅ Resolved` tag to your post.", ephemeral=True
        )


class Dismiss(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Dismiss", style=nextcord.ButtonStyle.grey, custom_id="dismiss_initial")
    async def dismiss(self, button: ui.Button, interaction: Interaction):
        """
        Dismiss the initial thread message.
        """
        await interaction.message.delete()


class Threads(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @slash_command(name="resolve", description="Mark a thread as resolved and archive it.")
    async def resolve(self, interaction: Interaction):
        """
        Mark a thread as resolved to archive it.
        Works in both forum threads and text channel threads.
        """
        if not isinstance(interaction.channel, nextcord.Thread):
            await interaction.response.send_message(
                "This command can only be used inside a thread.",
                ephemeral=True
            )
            return

        embed = Embed(title="", color=blue)
        embed.add_field(
            name="Resolved ✅",
            value=f"Post marked as resolved by {interaction.user.mention}."
        )

        await interaction.response.send_message(embed=embed)

        parent = interaction.channel.parent
        resolved_tag = None

        # Only try to get forum tag if parent has tags
        if hasattr(parent, "available_tags"):
            resolved_tag = nextcord.utils.get(parent.available_tags, name="Resolved")

        if resolved_tag:
            try:
                await interaction.channel.add_tags(resolved_tag)
            except Exception:
                pass  # Tag might not be applicable or may already exist

        try:
            await interaction.channel.edit(archived=True)
        except Exception:
            await interaction.followup.send("Failed to archive the thread.", ephemeral=True)


    @commands.Cog.listener()
    async def on_thread_create(self, thread: nextcord.Thread):
        """
        - Sends initial message in forum post when created with option to dismiss.
        - After 10 minutes, provides an option to ping helpers.
        """
        if thread.parent.name in ["modmail", "important-updates"]:
            return

        await asyncio.sleep(1)
        try:
            await thread.starter_message.pin()
        except Exception:
            pass

        thread_embed = Embed(title="", color=blue)
        thread_embed.add_field(
            name="Guidelines",
            value=(
                "Be sure you are following our rules and guidelines!\n"
                "- If you haven't already, send your attempts at a solution.\n"
                "- Also be sure that your title is following the `[Topic] question` format."
            ),
            inline=False
        )
        thread_embed.add_field(
            name="Resolved",
            value="Once your question has been answered, please mark your thread as `✅ Resolved`.",
            inline=False
        )
        thread_embed.add_field(
            name="Help",
            value="You will be able to ping helpers after 10 minutes.",
            inline=False
        )

        await thread.send(embed=thread_embed, view=Dismiss())

        await asyncio.sleep(600)  # 10 minutes
        help_embed = Embed(color=blue)
        help_embed.add_field(
            name="",
            value="If help is still needed, you may ping helpers now.",
            inline=False
        )

        await thread.starter_message.reply(embed=help_embed, view=PingHelpers())

    @commands.Cog.listener()
    async def on_thread_update(self, before: nextcord.Thread, after: nextcord.Thread):
        """
        If thread is updated with "Resolved" tag, then thread is archived.
        """
        if not after.applied_tags:
            return  # Not a forum thread, or no tags available

        tag_names = [tag.name for tag in after.applied_tags]
        if "Resolved" in tag_names:
            await after.edit(archived=True)



def setup(bot: commands.Bot):
    bot.add_cog(Threads(bot))
