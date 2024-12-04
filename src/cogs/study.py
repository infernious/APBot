import asyncio
import time
import nextcord
from typing import Union

from nextcord import Interaction, SlashOption, slash_command
from nextcord.ext import tasks, commands
from nextcord.ui import Button

from bot_base import APBot
from cogs.utils import convert_time

blue = 0x00ffff

class QuestionConfirm(nextcord.ui.View):

    def __init__(self, bot, message, inter):
        super().__init__(timeout=None)
        self.bot = bot
        self.message = message
        self.inter = inter

    @nextcord.ui.button(label='Confirm!', style=nextcord.ButtonStyle.green)
    async def callback(self, button: Button, interaction):

        """
        Confirm mention after command is used as to avoid accidental pings.
        Additionally ensures that the person who presses the button isn't some random goober who isn't the original person that used the command.
        """

        if interaction.user.id != self.inter.user.id:
            await interaction.response.send_message("You're not the one who asked the question!", ephemeral=True)
            return

        for role in [i for i in self.inter.guild.roles if i in self.inter.channel.overwrites]:
            if "Helper" in role.name:
                await self.message.reply(f"{role.mention}, a question has been asked!")

        button.style = nextcord.ButtonStyle.green
        button.emoji = '✅'
        button.label = "Helpers pinged!"
        button.disabled = True

        await interaction.response.edit_message(view=self)

        self.stop()

    async def on_timeout(self) -> None:

        self.callback.style = nextcord.ButtonStyle.grey
        self.callback.label = "Timed out!"
        self.callback.disabled = True

        await self.message.edit(view=self)

class Study(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot
        self.cooldowns = {}
        self.check_studiers.start()

        self.pin_ctx_menu = nextcord.application_commands.ContextMenu(
            name="Pin Message",
            callback=self.pin
        )
        self.bot.tree.add_command(self.pin_ctx_menu)

        self.unpin_ctx_menu = nextcord.app_commands.ContextMenu(
            name="Unpin Message",
            callback=self.unpin
        )
        self.bot.tree.add_command(self.unpin_ctx_menu)

    @slash_command(name='question', description='Ask a question in a subject channel.')
    async def question(self, interaction: nextcord.Interaction, question: str, attachment: nextcord.Attachment = None):
        

        """
        Ping helpers in a subject channel after 10 minutes the command is used.
            - Checks if question is in subject channel.
            - Checks if question is "good" if its length is more than 5 words (to avoid users from just saying "help", "above", "^" or something along those lines.
            - Waits 10 minutes for question to be answered.
            - Prompts user after 10 minutes to confirm pinging helpers in the event that they have not been helped yet. 
            - Uses QuestionConfirm().
        """

        user_id = interaction.user.id
        current_time = time.time()
        cooldown_duration = 60.0 # Set command cooldown as 60 seconds  
        if user_id in self.cooldowns:
            elapsed_time = current_time - self.cooldowns[user_id]
            if elapsed_time < cooldown_duration:
                await interaction.response.send_message(
                    f"Command on cooldown. Try again in {round(cooldown_duration - elapsed_time, 2)} seconds.",
                    ephemeral=True
                )
                return

        self.cooldowns[user_id] = current_time

        subject_channels = nextcord.utils.get(interaction.guild.categories, name="Subject Channels")

        if interaction.channel.category != subject_channels:
            raise commands.CommandError("Please ask a question in the subject channels.")

        if len(question.split()) <= 5:
            raise commands.CommandError("Please restate your question to have more than 5 words."
                                               " Don't ask to ask, just post your question! "
                                               "Be sure to include what you've tried as well.\n \n"
                                               "Example: /question What is the powerhouse of the cell? \n \n"
                                               "You can also post an image with your question if need be.")

        question_embed = nextcord.Embed(title="", color=blue)
        question_embed.add_field(name="Question:", value=f"```{question}```")

        if attachment:
            question_embed.set_image(url=attachment.proxy_url)

        skibidi_time = int(time.time()) + 600
        await interaction.response.send_message(f"{interaction.user.mention} has asked a question! "
                                                f"You are able to ping helpers after <t:{skibidi_time}:R> "
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
        await ping_helpers.edit(view=
        QuestionConfirm(self.bot, ping_helpers, interaction))

    async def remove_study_role(self, user_id: int) -> None:
        try:
            user = await self.bot.getch_member(self.bot.guild.id, user_id)
            for role in self.bot.guild.roles:
                if role.name == "Study":
                    study_role_id = role.id
            role = await self.bot.getch_role(self.bot.guild.id, study_role_id)
        except:
            return

        if not user or not role:
            return

        await self.bot.db.study.delete_user(user_id)
        await user.remove_roles(role)
    
    @slash_command(name='potd', description='Make a problem-of-the-day for a subject channel.')
    async def potd(self, interaction: nextcord.Interaction, title: str, problem: str, attachment: nextcord.Attachment = None):

        """
        Submit a problem-of-the-day in a subject channel.
            - Checks if POTD is in subject channel.
            - Edits the channel topic with the number of POTDs.
            - Creates a thread for the POTD.
            - Removes all past POTDs if they haven't been removed yet.
        """

        user_id = interaction.user.id
        current_time = time.time()
        cooldown_duration = 86400 # Set command cooldown as 60 seconds  
        if user_id in self.cooldowns:
            elapsed_time = current_time - self.cooldowns[user_id]
            if elapsed_time < cooldown_duration:
                await interaction.response.send_message(
                    f"Command on cooldown. Try again in {round(cooldown_duration - elapsed_time, 2)} seconds.",
                    ephemeral=True
                )
                return

        self.cooldowns[user_id] = current_time

        subject_channels = nextcord.utils.get(interaction.guild.categories, name="Subject Channels")

        if interaction.channel.category != subject_channels:
            raise nextcord.app_commands.AppCommandError("Please provide a POTD only in the subject channels.")

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

        potd_embed = nextcord.Embed(title=f"", color=blue)
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
    

    @slash_command(name="study", description="Prevent yourself from viewing unhelpful channels.")
    async def study(
        self,
        inter: Interaction,
        duration: str = SlashOption("duration", description="Reminder duration. Format: 5h9m2s", required=True),
    ):
        """
        Gives member the study role to prevent distraction/procrastination.
            - Checks if time is greater than or equal to 10 minutes.
            - Gives study role to member.
            - Updates user document in the database collection with datetime to remove the study role.
        """
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

        for role in inter.guild.roles:
            if role.name == "Study":
                study_role_id = role.id

        if study_role_id in [i.id for i in inter.user.roles]:
            await resp.edit("Removing role...")
            await self.remove_study_role(inter.user.id)

        await inter.user.add_roles(await self.bot.getch_role(self.bot.guild.id, study_role_id))
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

        @nextcord.ui.button(label = 'Yes', style=nextcord.ButtonStyle.green)
        async def remove_role(self, button: nextcord.ui.Button, inter: nextcord.Interaction):
            self.value = True
            self.stop()

        @nextcord.ui.button(label = 'No', style=nextcord.ButtonStyle.red)
        async def dont_remove_role(self, button: nextcord.ui.Button, inter: nextcord.Interaction):
            self.value = False
            self.stop()

    @slash_command(name="remove_study_role", description="Allow yourself to view channels once again (remove study role).")
    async def remove_study(
        self,
        inter: Interaction
    ):
        """
        Allow member to remove their study role (if they have it) if they are done with their studying.
            - Checks first if study role is at all present.
                - If present, proceed:
                    - Asks user to confirm the removal of the study role.
                    - If yes:
                        - Removes study role from member.
                        - Remove member's entry from database.
                        - Allows them to access all channels once again.
                    - If no, does nothing.
                    - If button view times out, does nothing as well.
                - If not, do nothing.
        """

        await inter.response.defer(ephemeral=True)

        for role in inter.guild.roles:
            if role.name == "Study":
                study_role_id = role.id

        if study_role_id not in [i.id for i in inter.user.roles]:
            return await inter.followup.send("You do not have a study role to remove!")

        view = self.ConfirmDeny()

        resp = await inter.send("Are you sure you want to remove your study role early?", ephemeral=True, view=view)

        await view.wait()

        if view.value:
            await resp.edit("Removing role...", view=None)
            await self.remove_study_role(inter.user.id)
            return await resp.edit("Successfully removed role! You now have access to channels again.", view=None)
        return await resp.edit("Request cancelled.", view=None)
    
    @commands.Cog.listener()
    async def on_ready(self) -> None:
        students = await self.bot.db.study.get_all()
        for user_id, expires_at in students.items():
            seconds = expires_at - int(time.time())
            if seconds <= 0:
                await self.remove_study_role(user_id)
            else:
                self.bot.loop.call_later(seconds, asyncio.create_task, self.remove_study_role(user_id))

    @nextcord.app_commands.checks.has_role("Honorable")
    async def pin(self, interaction: nextcord.Interaction, message: nextcord.Message):

        """
        Pins a message using the bot.
        """

        await message.pin()
        embed = nextcord.Embed(color=blue)
        embed.add_field(name="Pinned! ✔", value="Message successfully pinned.")
        await interaction.response.send_message(embed=embed)

    @nextcord.app_commands.checks.has_role("Honorable")
    async def unpin(self, interaction: nextcord.Interaction, message: nextcord.Message):

        """
        Unpins a message using the bot.
        """

        await message.unpin()
        embed = nextcord.Embed(color=blue)
        embed.add_field(name="Unpinned! ✔", value="Message successfully unpinned.")
        await interaction.response.send_message(embed=embed)

    @tasks.loop(minutes=5)
    async def check_studiers(self):

        """
        Checks every 5 minutes if any study roles need to be removed.
        """

        guild = self.bot.get_guild(self.bot.guild_id)
        cursor = self.bot.user_config.find({"study_time_until": {"$lte": time.datetime.now()}})
        documents = await cursor.to_list(length=100)

        for document in documents:
            member = guild.get_member(document["user_id"])
            role = nextcord.utils.get(guild.roles, name="Study")

            if role in member.roles:
                await member.remove_roles(role)

            await self.bot.user_config.update_one({"_id": document["_id"]}, {"$unset": {"study_time_until": ""}})

    @check_studiers.before_loop
    async def check_studiers_before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Study(bot), guilds=[nextcord.Object(id=bot.guild_id)])