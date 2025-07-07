import datetime
import time
import asyncio
import nextcord

from nextcord import Interaction, Embed, Attachment, Message, slash_command, SlashOption
from nextcord.ext import commands
from typing import Union

from cogs.utils import convert_time

blue = nextcord.Color.teal()


class QuestionConfirm(nextcord.ui.View):
    def __init__(self, bot, message, asker_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.message = message
        self.asker_id = asker_id

    @nextcord.ui.button(label="Confirm!", style=nextcord.ButtonStyle.green)
    async def confirm_button(self, button: nextcord.ui.Button, interaction: Interaction):
        if interaction.user.id != self.asker_id:
            await interaction.response.send_message(
                "Only the user who asked the question can confirm pinging helpers.",
                ephemeral=True
            )
            return

        for role in interaction.channel.changed_roles:
            if "Helper" in role.name:
                await self.message.reply(f"{role.mention}, a question has been asked!")

        button.style = nextcord.ButtonStyle.green
        button.emoji = "✅"
        button.label = "Helpers pinged!"
        button.disabled = True

        await interaction.response.edit_message(view=self)
        self.stop()




class Study(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_topic_update = {}
        self.potd_cooldowns = {}
        

    @slash_command(name="question", description="Ask a question in a subject channel.")
    async def question(
        self,
        inter: Interaction,
        question: str = SlashOption(description="Your question", required=True),
        attachment: Attachment = SlashOption(description="Optional image", required=False, default=None)
    ):
        subject_channels = nextcord.utils.get(inter.guild.categories, name="Subject Channels")
        if inter.channel.category != subject_channels:
            await inter.response.send_message(
                "Please ask a question in the subject channels.", ephemeral=True
            )
            return

        if len(question.split()) <= 5:
            await inter.response.send_message(
                "Please restate your question to have more than 5 words.\n"
                "Don't ask to ask, just post your question! Be sure to include what you've tried.\n\n"
                "Example: /question What is the powerhouse of the cell?\n"
                "You can also post an image with your question if needed.",
                ephemeral=True
            )
            return

        # Create question embed
        question_embed = Embed(title="", color=blue)
        question_embed.add_field(name="Question:", value=f"```{question}```")
        if attachment:
            question_embed.set_image(url=attachment.proxy_url)

        # Send initial message with auto-delete in 10 mins
        await inter.response.send_message(
            f"{inter.user.mention} has asked a question! "
            "You are able to ping helpers after 10 minutes *if you have not been helped*.",
            embed=question_embed,
            delete_after=600
        )

        # Wait for 10 minutes before enabling "Ping Helpers!" message
        await asyncio.sleep(600)

        # Add the ping helpers instruction and button
        question_embed.add_field(
            name="Ping Helpers!",
            value="**If help is needed**, you can now ping helpers. Make sure your question is detailed and you've shown your thought process.",
            inline=False
        )

        ping_msg = await inter.channel.send(f"{inter.user.mention}", embed=question_embed)
        await ping_msg.edit(view=QuestionConfirm(self.bot, ping_msg, inter.user.id))



    @slash_command(name="potd", description="Make a problem-of-the-day for a subject channel.")
    async def potd(
        self,
        inter: Interaction,
        title: str = SlashOption(description="Title of the POTD"),
        problem: str = SlashOption(description="Problem statement"),
        attachment: Attachment = SlashOption(description="Optional image", required=False, default=None)
    ):
        subject_channels = nextcord.utils.get(inter.guild.categories, name="Subject Channels")
        if inter.channel.category != subject_channels:
            await inter.response.send_message(
                "Please provide a POTD only in the subject channels.", ephemeral=True
            )
            return

        now = datetime.datetime.utcnow()
        cooldown_key = (inter.user.id, inter.channel.id)
        last_used = self.potd_cooldowns.get(cooldown_key)

        if last_used and (now - last_used).total_seconds() < 86400:  # 24 hours 86400
            remaining = int(86400 - (now - last_used).total_seconds())
            await inter.response.send_message(
                f"⏳ You already posted a POTD in this channel. Try again in {remaining // 3600}h {(remaining % 3600) // 60}m.",
                ephemeral=True
            )
            return

        self.potd_cooldowns[cooldown_key] = now

        # Update topic count
        try:
            topic_split = inter.channel.topic.split()
            count = int(topic_split[-1]) + 1
            topic_split[-1] = str(count)
            new_topic = " ".join(topic_split)
        except (ValueError, AttributeError):
            count = 1
            new_topic = "POTD Count: 1" if not inter.channel.topic else f"{inter.channel.topic} | POTD Count: {count}"

        last_edit = self.last_topic_update.get(inter.channel.id)
        if not last_edit or (now - last_edit).total_seconds() > 600:  # 10 minute rate limit
            try:
                await inter.channel.edit(topic=new_topic)
                self.last_topic_update[inter.channel.id] = now
            except nextcord.HTTPException as e:
                if e.status == 429:
                    await inter.followup.send("Could not update topic due to rate limits.", ephemeral=True)
                else:
                    raise
        else:
            await inter.followup.send("Skipping topic update to avoid rate limit.", ephemeral=True)

        potd_embed = Embed(title="", color=blue)
        potd_embed.add_field(name=f"POTD #{count}: {title}", value=f"```{problem}```")
        if attachment:
            potd_embed.set_image(url=attachment.proxy_url)

        await inter.response.send_message(embed=potd_embed)
        potd_msg = await inter.original_message()

        await inter.channel.create_thread(
            name=f"POTD #{count}: {title}",
            message=potd_msg,
            reason=f"#{inter.channel.name} POTD #{count}: {title}"
        )



    async def remove_study_role(self, user_id: int) -> None:
        try:
            guild = await self.bot.fetch_guild(self.bot.config.get("guild_id"))
            user = await self.bot.getch_member(guild.id, user_id)
            study_role = nextcord.utils.get(guild.roles, name="Study")
        except:
            return

        if not user or not study_role:
            return

        await self.bot.db.study.delete_user(user_id)
        await user.remove_roles(study_role)

    @slash_command(name="study", description="Prevent yourself from viewing unhelpful channels.")
    async def study(
        self,
        inter: Interaction,
        duration: str = SlashOption("duration", description="Reminder duration. Format: 5h9m2s", required=True),
    ):
        await inter.response.defer(ephemeral=True)
        resp = await inter.send("Validating time input...", ephemeral=True)

        duration: Union[str, int] = convert_time(duration)
        if isinstance(duration, str):
            return await resp.edit(content=duration)

        if duration < 60 * 10:
            return await resp.edit("Please set a duration greater than 10 minutes!")
        if duration > 60 * 60 * 24 * 7:
            return await resp.edit("Please set a duration lesser than a week")

        await resp.edit("Performing actions...")
        study_end = int(time.time()) + duration

        guild = await self.bot.fetch_guild(self.bot.config.get("guild_id"))
        study_role = nextcord.utils.get(guild.roles, name="Study")
        if study_role.id in [role.id for role in inter.user.roles]:
            await resp.edit("Removing role...")
            await self.remove_study_role(inter.user.id)

        await inter.user.add_roles(study_role)
        await resp.edit("Updating database...")

        await self.bot.db.study.set_time(inter.user.id, study_end)

        self.bot.loop.call_later(duration, asyncio.create_task, self.remove_study_role(inter.user.id))
        await resp.edit(
            f"The study role will be removed <t:{study_end}:R> at <t:{study_end}:f>."
        )

    class ConfirmDeny(nextcord.ui.View):
        def __init__(self) -> None:
            super().__init__(timeout=30)
            self.value = None

        @nextcord.ui.button(label='Yes', style=nextcord.ButtonStyle.green)
        async def remove_role(self, button: nextcord.ui.Button, inter: nextcord.Interaction):
            self.value = True
            self.stop()

        @nextcord.ui.button(label='No', style=nextcord.ButtonStyle.red)
        async def dont_remove_role(self, button: nextcord.ui.Button, inter: nextcord.Interaction):
            self.value = False
            self.stop()


def setup(bot):
    bot.add_cog(Study(bot))
