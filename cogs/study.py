from nextcord.ext import commands
from nextcord import slash_command, Interaction, Button, ButtonStyle, Attachment, Embed, Message, Object
import nextcord
from bot_base import APBot
import re

class QuestionConfirm(nextcord.ui.View):
    def __init__(self, bot: APBot, message):
        super().__init__(timeout=None)
        self.bot = bot
        self.message = message

    @nextcord.ui.button(label='Confirm!', style=ButtonStyle.green)
    async def callback(self, interaction: Interaction, button: Button):
        """
        Confirm mention after command is used as to avoid accidental pings.
        """

        for role in interaction.channel.changed_roles:
            if "Helper" in role.name:
                await self.message.reply(f"{role.mention}, a question has been asked!")

        button.style = ButtonStyle.green
        button.emoji = '✅'
        button.label = "Helpers pinged!"
        button.disabled = True

        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self) -> None:
        self.callback.style = ButtonStyle.grey
        self.callback.label = "Timed out!"
        self.callback.disabled = True

        await self.message.edit(view=self)


class Study(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot
        self.potd_count_re = re.compile(r"POTD Count: [0-9]{1,3}")

    @slash_command(name="question", description="Ask a question in a subject channel.")
    @commands.cooldown(1, 60)
    async def question(self, interaction: Interaction, question: str, attachment: Attachment = None):
        """
        Ping helpers in a subject channel after 10 minutes the command is used.
            - Checks if question is in subject channel.
            - Checks if question is "good" if its length is more than 5 words (to avoid users from just saying "help", "above", "^" or something along those lines.
            - Waits 10 minutes for question to be answered.
            - Prompts user after 10 minutes to confirm pinging helpers in the event that they have not been helped yet.
            - Uses QuestionConfirm().
        """

        if interaction.channel.category != self.bot.config.get("subject_category_id"):
            raise commands.AppCommandError("Please ask a question in the subject channels.")

        if len(question.split()) <= 5:
            return interaction.response.send_message("""
                Please restate your question to have more than 5 words.
                Don't ask to ask, just post your question! 
                Be sure to include what you've tried as well.

                Example: /question What is the powerhouse of the cell?

                You can also post an image with your question if need be.
                """.strip(),
                ephemeral=True
            )

        question_embed = Embed(title="", color=self.bot.colors["blue"])
        question_embed.add_field(name="Question:", value=f"```{question}```")

        if attachment:
            question_embed.set_image(url=attachment.proxy_url)

        await interaction.response.send_message(
            content=f"{interaction.user.mention} has asked a question! If you do not receive help within 10 minutes, you will be able to ping the helpers.",
            embed=question_embed,
            delete_after=600,
        )

        def check(m: Message):
            return m.author.id == self.bot.application_id

        await self.bot.wait_for("message_delete", check=check)

        question_embed.add_field(
            name="Ping Helpers!",
            value="""
            **If help is still required**, you can now ping helpers.
            Please ensure you **clearly state your question** and show your **thought process**
            To ping helpers, confirm with the buttom below.
            """.strip(),
            inline=False,
        )

        ping_helpers = await interaction.channel.send(interaction.user.mention, embed=question_embed)
        await ping_helpers.edit(view=QuestionConfirm(self.bot, ping_helpers))

    @slash_command(name="potd", description="Make a problem-of-the-day for a subject channel.")
    @commands.cooldown(1, 86400, commands.BucketType.channel)
    async def potd(self, interaction: Interaction, title: str, problem: str, attachment: Attachment = None):
        """
        Submit a problem-of-the-day in a subject channel.
            - Checks if POTD is in subject channel.
            - Edits the channel topic with the number of POTDs.
            - Creates a thread for the POTD.
            - Removes all past POTDs if they haven't been removed yet.
        """

        if interaction.channel.category != self.bot.config.get("subject_category_id"):
            raise commands.AppCommandError("Please provide a POTD only in the subject channels.")

        potd_count = self.potd_count_re.findall(interaction.channel.topic)
        if potd_count:
            potd_count = int(potd_count[0].split(" ")[-1]) + 1
            new_channel_topic = interaction.channel.topic.replace(f"POTD Count: {potd_count-1}", f"POTD Count: {potd_count}")
        else:
            potd_count = 1
            new_channel_topic = interaction.channel.topic + f" | POTD Count: 1"

        await interaction.channel.edit(topic=new_channel_topic)

        thread_topic = f"POTD #{potd_count}: {title}"

        potd_embed = Embed(title=title, description=f"```{problem}```", color=self.bot.colors.get("blue"))
        if attachment:
            potd_embed.set_image(url=attachment.proxy_url)

        potd_message = await interaction.channel.send(content=thread_topic, embed=potd_embed)
        await potd_message.create_thread(name=thread_topic)

        pins = await interaction.channel.pins()
        for message in pins:
            if not message.embeds or "POTD" not in message.embeds[0].fields[0].name.split():
                continue

            await message.unpin()

        await potd_message.pin()

async def setup(bot: APBot):
    await bot.add_cog(Study(bot), guilds=[Object(id=bot.guild_id)])
