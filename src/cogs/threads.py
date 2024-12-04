import nextcord
from nextcord import app_commands
from nextcord.ext import commands
import asyncio

blue = 0x00ffff


class PingHelpers(nextcord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label='Ping Helpers!', style=nextcord.ButtonStyle.red)
    async def callback(self, interaction, button):

        """
        Confirm mention after command is used as to avoid accidental pings.
        - Currently uses subject tags to find the helper role
            • Needs to be optimized and, if forums are further split, rewritten.
        """

        button.style = nextcord.ButtonStyle.green
        button.emoji = '✅'
        button.label = "Helpers pinged!"
        button.disabled = True
        self.dismiss.disabled = True

        await interaction.response.edit_message(view=self)

        helpers = []
        for tag in interaction.channel.applied_tags:
            try:
                helpers.append(nextcord.utils.get(interaction.guild.roles, name=f'{tag} Helper'))
            except:
                continue

        try:
            pins = await interaction.channel.pins()
            await pins[0].reply(f"{helpers[0].mention}, a question has been asked!")
            self.stop()
        except:
            await interaction.response.send_message(f"Please edit your post to have a subject tag first.", ephemeral=True)

    @nextcord.ui.button(label='Dismiss', style=nextcord.ButtonStyle.grey)
    async def dismiss(self, interaction, button):

        """
        Dismiss options to ping helpers.
        """

        await interaction.message.delete()
        await interaction.response.send_message(f"Please add the `✅ Resolved` tag to your post.", ephemeral=True)


class Dismiss(nextcord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @nextcord.ui.button(label='Dismiss', style=nextcord.ButtonStyle.grey)
    async def dismiss(self, interaction, button):

        """
        Dismiss the initial thread message.
        """

        await interaction.message.delete()


class Threads(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name='resolve', description='Mark a forum post as resolved and archive it.')
    async def resolve(self, interaction: nextcord.Interaction):

        """
        Mark a thread as resolved to archive it.
            - Allows non-authors to resolve a post.
        """

        resolve_embed = nextcord.Embed(title='', color=blue)
        resolve_embed.add_field(name='Resolved ✅', value=f'Post marked as resolved by {interaction.user.mention}.')
        await interaction.response.send_message(embed=resolve_embed)

        resolve_tag = nextcord.utils.get(interaction.channel.parent.available_tags, name='Resolved')
        await interaction.channel.add_tags(resolve_tag)
        await interaction.channel.edit(archived=True)


    @commands.Cog.listener()
    async def on_thread_create(self, thread):

        """
        - Sends initial message in forum post when created with option to dismiss.
        - After 10 minutes, provides an option to ping helpers.
        """

        if thread.parent.name == "modmail" or thread.parent.name == "important-updates":
            return

        await asyncio.sleep(1)
        await thread.starter_message.pin()

        thread_embed = nextcord.Embed(title='', color=blue)
        thread_embed.add_field(name='Guidelines', inline=False, value="""Be sure you are following our rules and guidelines!
                                                                      - If you haven't already, send your attempts at a solution.
                                                                      - Also be sure that your title is following the `[Topic] question` format.""")
        thread_embed.add_field(name='Resolved', inline=False, value="Once your question has been answered, please mark your thread as `✅ Resolved`.")
        thread_embed.add_field(name='Help', inline=False, value="You will be able to ping helpers after 10 minutes.")

        await thread.send(embed=thread_embed, view=Dismiss())

        await asyncio.sleep(600)
        help_embed = nextcord.Embed(title='', color=blue)
        help_embed.add_field(name='', inline=False, value='If help is still needed, you may ping helpers now.')
        await thread.starter_message.reply(embed=help_embed, view=PingHelpers())

    @commands.Cog.listener()
    async def on_thread_update(self, before, after):

        """
        If thread is updated with "Resolved" tag, then thread is archived.
        """

        tags = [tag.name for tag in after.applied_tags]
        if "Resolved" in tags:
            await after.edit(archived=True)


async def setup(bot):
    await bot.add_cog(Threads(bot), guilds=[nextcord.Object(id=bot.guild_id)])