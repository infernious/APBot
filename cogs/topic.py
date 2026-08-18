import json
import os
import random

import discord
from discord import app_commands
from discord.ext import commands

blue = 0x00ffff

QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "topic_questions.json")


class Topic(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_question_by_channel: dict[int, str] = {}
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            self.questions = json.load(f)

    @app_commands.checks.cooldown(1, 300, key=lambda i: i.channel_id)
    @app_commands.command(name='topic', description='Start a random conversation topic in the channel.')
    async def topic(self, interaction: discord.Interaction):

        """
        Posts a random question from the curated question bank in the current channel.
            - Pulls a random question from topic_questions.json.
            - Avoids picking the same question twice in a row in the same channel.
            - Refuses to run in subject channels (where it would be off-topic).
            - Posts as an embed with a 5 minute per-channel cooldown to prevent spam.
        """

        # Block use in subject channels so this stays out of the way of /question and /potd.
        if interaction.channel.category and interaction.channel.category.name == "Subject Channels":
            raise app_commands.AppCommandError(
                "The /topic command is meant for general chat. "
                "Please use it in #general-1 or a similar off-topic channel."
            )

        if not self.questions:
            raise app_commands.AppCommandError("The topic question bank is empty. Please contact a moderator.")

        last_question = self._last_question_by_channel.get(interaction.channel_id)

        question = random.choice(self.questions)

        # Try a few times to avoid repeating the last question in this channel.
        attempts = 0
        while question == last_question and len(self.questions) > 1 and attempts < 10:
            question = random.choice(self.questions)
            attempts += 1

        self._last_question_by_channel[interaction.channel_id] = question

        topic_embed = discord.Embed(title="", color=blue)
        topic_embed.add_field(name="Random Topic...", value=f"```{question}```", inline=False)
        topic_embed.set_footer(text=f"Started by {interaction.user.display_name} , Drop your answer below!")

        await interaction.response.send_message(embed=topic_embed)


async def setup(bot):
    await bot.add_cog(Topic(bot), guilds=[discord.Object(id=bot.guild_id)])

