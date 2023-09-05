import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.commands import convert

blue = 0x00ffff

class QuestionConfirm(discord.ui.View):

    def __init__(self, bot, message):
        super().__init__(timeout=None)
        self.bot = bot
        self.message = message

    @discord.ui.button(label='Confirm!', style=discord.ButtonStyle.green)
    async def callback(self, interaction, button):

        """
        Confirm mention after command is used as to avoid accidental pings.
        """

        for role in interaction.channel.changed_roles:
            if "Helper" in role.name:
                await self.message.reply(f"{role.mention}, a question has been asked!")

        button.style = discord.ButtonStyle.green
        button.emoji = '✅'
        button.label = "Helpers pinged!"
        button.disabled = True

        await interaction.response.edit_message(view=self)

        self.stop()

    async def on_timeout(self) -> None:

        self.callback.style = discord.ButtonStyle.grey
        self.callback.label = "Timed out!"
        self.callback.disabled = True

        await self.message.edit(view=self)


class Study(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        self.pin_ctx_menu = app_commands.ContextMenu(
            name="Pin Message",
            callback=self.pin
        )
        self.bot.tree.add_command(self.pin_ctx_menu)

        self.unpin_ctx_menu = app_commands.ContextMenu(
            name="Unpin Message",
            callback=self.unpin
        )
        self.bot.tree.add_command(self.unpin_ctx_menu)

    @app_commands.checks.cooldown(1, 60)
    @app_commands.command(name='question', description='Ask a question in a subject channel.')
    async def question(self, interaction: discord.Interaction, question: str, attachment: discord.Attachment = None):

        """
        Ping helpers in a subject channel after 10 minutes the command is used.
            - Checks if question is in subject channel.
            - Checks if question is "good" if its length is more than 5 words (to avoid users from just saying "help", "above", "^" or something along those lines.
            - Waits 10 minutes for question to be answered.
            - Prompts user after 10 minutes to confirm pinging helpers in the event that they have not been helped yet.
            - Uses QuestionConfirm().
        """

        subject_channels = discord.utils.get(interaction.guild.categories, name="Subject Channels")

        if interaction.channel.category != subject_channels:
            raise app_commands.AppCommandError("Please ask a question in the subject channels.")

        if len(question.split()) <= 5:
            raise app_commands.AppCommandError("Please restate your question to have more than 5 words."
                                               " Don't ask to ask, just post your question! "
                                               "Be sure to include what you've tried as well.\n \n"
                                               "Example: /question What is the powerhouse of the cell? \n \n"
                                               "You can also post an image with your question if need be.")

        question_embed = discord.Embed(title="", color=blue)
        question_embed.add_field(name="Question:", value=f"```{question}```")

        if attachment:
            question_embed.set_image(url=attachment.proxy_url)

        await interaction.response.send_message(f"{interaction.user.mention} has asked a question! "
                                                f"You are able to ping helpers after 10 minutes "
                                                f"*if you have not been helped*.",
                                                embed=question_embed,
                                                delete_after=600)

        def check(m):
            return m.author.id == self.bot.application_id

        await self.bot.wait_for('message_delete', check=check)

        question_embed.add_field(name="Ping Helpers!",
                                 value="**If help is needed**, you can now ping helpers. Be sure that you have "
                                       "crafted a **well-developed question** and have shown your **thought "
                                       "process**. To ping helpers, confirm with the buttom below.",
                                 inline=False)

        ping_helpers = await interaction.channel.send(f"{interaction.user.mention}", embed=question_embed)
        await ping_helpers.edit(view=QuestionConfirm(self.bot, ping_helpers))

    @app_commands.checks.cooldown(1, 86400, key=lambda i: i.channel_id)
    @app_commands.command(name='potd', description='Make a problem-of-the-day for a subject channel.')
    async def potd(self, interaction: discord.Interaction, title: str, problem: str, attachment: discord.Attachment = None):

        """
        Submit a problem-of-the-day in a subject channel.
            - Checks if POTD is in subject channel.
            - Edits the channel topic with the number of POTDs.
            - Creates a thread for the POTD.
            - Removes all past POTDs if they haven't been removed yet.
        """

        subject_channels = discord.utils.get(interaction.guild.categories, name="Subject Channels")

        if interaction.channel.category != subject_channels:
            raise app_commands.AppCommandError("Please provide a POTD only in the subject channels.")

        try:
            topic_split = interaction.channel.topic.split()
            count = int(topic_split[-1]) + 1
            topic_split[-1] = f"{count}"
            new_topic = ' '.join(topic_split)
        except ValueError:
            count = 1
            new_topic = f"{interaction.channel.topic} | POTD Count: {count}"
        except AttributeError:
            count = 1
            new_topic = "POTD Count: 1"
        await interaction.channel.edit(topic=new_topic)

        potd_embed = discord.Embed(title=f"", color=blue)
        potd_embed.add_field(name=f"POTD #{count}: {title}", value=f"```{problem}```")
        if attachment:
            potd_embed.set_image(url=attachment.proxy_url)

        await interaction.response.send_message(embed=potd_embed)
        potd_message = await interaction.original_response()
        await interaction.channel.create_thread(name=f"POTD #{count}: {title}", message=potd_message,
                                                reason=f"#{interaction.channel.name} POTD #{count}: {title}")

        pins = await interaction.channel.pins()
        pins = pins[::1]
        for message in pins:
            if message.embeds:
                if "POTD" in message.embeds[0].fields[0].name.split():
                    await message.unpin()
        await potd_message.pin()

    @app_commands.checks.has_role("Honorable")
    async def pin(self, interaction: discord.Interaction, message: discord.Message):

        """
        Pins a message using the bot.
        """

        await message.pin()
        embed = discord.Embed(color=blue)
        embed.add_field(name="Pinned! ✔", value="Message successfully pinned.")
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_role("Honorable")
    async def unpin(self, interaction: discord.Interaction, message: discord.Message):

        """
        Unpins a message using the bot.
        """

        await message.unpin()
        embed = discord.Embed(color=blue)
        embed.add_field(name="Unpinned! ✔", value="Message successfully unpinned.")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Study(bot), guilds=[discord.Object(id=bot.guild_id)])
