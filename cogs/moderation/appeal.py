from nextcord import Embed, Message, Object, errors, ui, TextInputStyle, Interaction, ButtonStyle, slash_command
from nextcord.ext import commands, tasks, application_checks
from typing import Optional

from bot_base import APBot
import asyncio
from datetime import datetime
import time

async def generic_decide(bot: APBot, user_id: int, message_id: int):
    appeal_message: Optional[Message] = await bot.getch_message(bot.config.get("appeals_channel_id"), message_id)

    maintain_ban_reactions = len([i for i in appeal_message.reactions if i.emoji == "🔴"])
    unban_reactions = len([i for i in appeal_message.reactions if i.emoji == "🟢"])

    decision_embed = Embed(title="")

    if unban_reactions > maintain_ban_reactions:
        try:
            decision_embed.colour = bot.colors["green"]
            decision_embed.add_field(name="", value="Member will be unbanned!")
            await bot.guild.unban(Object(id=user_id))
        except errors.NotFound:
            decision_embed.colour = bot.colors["orange"]
            decision_embed.add_field(name="", value="Member is already unbanned!")
        try:
            user = await bot.getch_user(user_id)
            await user.send(embed=Embed(title="Ban Lifted.", description="You have been unbanned from AP Students! Welcome back :)\nJoin back using [this link!](https://discord.gg/apstudents)", color=self.bot.colors["green"]))
        except:
            pass
    else:
        decision_embed.colour = bot.colors["red"]
        decision_embed.add_field(name="", value="Member will remain banned!")

    await appeal_message.thread.send(embed=decision_embed)
    await appeal_message.thread.edit(archived=True)


class BanAppealModal(ui.Modal):
    def __init__(self, bot: APBot):
        self.bot = bot
        super().__init__(
            title="Ban Appeal",
            custom_id="appeal_modal",
            timeout=None
        )

        self.appeal = ui.TextInput(
            label="Ban Appeal",
            style=TextInputStyle.paragraph,
            custom_id="appeal_modal_why",
            min_length=100,
            max_length=750,
            required=True,
            placeholder="Why should your ban be appealed? We recommend taking a few weeks to write a thoughful response.",
        )
        self.add_item(self.appeal)

        self.media = ui.TextInput(
            label = "Supporting Media",
            required=False,
            placeholder='Feel free to send links to supporting media here.',
            style=TextInputStyle.paragraph,
            custom_id="appeal_modal_media",
            max_length=150,
        )
        self.add_item(self.media)

        self.miscellaneous = ui.TextInput(
            label="Anything else?",
            required=False,
            placeholder='If there is anything else you would like to share, please do so below.',
            style=TextInputStyle.paragraph,
            custom_id="appeal_modal_misc",
            max_length=750,
        )

        self.add_item(self.miscellaneous)

    async def callback(self, inter: Interaction):
        await inter.response.defer(ephemeral=True, with_message=True)

        ch = await self.bot.getch_channel(self.bot.config.get("appeals_channel_id"))
        now = datetime.now()

        emb = Embed(
            title=f"{inter.user.name} ({inter.user.id})",
            description=f"```\n{self.appeal.value}\n```",
            color=self.bot.colors["light_orange"]
        )
        if self.media.value:
            emb.add_field(name="Media Links:", value=f"```\n{self.media.value}\n```", inline = False)
        if self.miscellaneous.value:
            emb.add_field(name="Additional Information:", value=f"```\n{self.miscellaneous.value}\n```", inline = False)

        appeal_message: Message = await ch.send(embed=emb)
        await appeal_message.add_reaction("🟢")
        await appeal_message.add_reaction("🟡")
        await appeal_message.add_reaction("🔴")
        await appeal_message.create_thread(name=f"{now.strftime('%m/%d/%Y')} - {inter.user.name}")

        await self.bot.db.set_user_appeal_submission(inter.user.id, now.timestamp(), appeal_message.id)

        self.bot.loop.call_later(
            60*60*24*7*2,
            asyncio.create_task,
            generic_decide(self.bot, inter.user.id, appeal_message.id)
        )

        await inter.followup.send(
            f"Your appeal has been sent. You will receive a response in 2 weeks",
            ephemeral=True
        )

    async def on_error(self, inter: Interaction, error: Exception) -> None:
        await inter.send(f'Oops! Something went wrong.\n{error}', ephemeral=True)



class BanAppealView(ui.View):
    def __init__(self, bot: APBot):
        self.bot = bot
        super().__init__(timeout=None)

    @ui.button(label='Appeal Ban', style=ButtonStyle.blurple, custom_id="appeal")
    async def callback(self, button: ui.Button, inter: Interaction):
        """
        Confirm to appeal ban to bring up the modal.
        """

        if inter.user.id in [i.id for i in self.bot.guild.members]:
            return await inter.send("You ain't banned...", ephemeral=True)

        last_appeal_time, decision = await self.bot.db.get_last_appeal(inter.user.id)
        if last_appeal_time:
            if decision is None: # less than 2 weeks past, no decision
                return await inter.send("Your last appeal is still being considered.", ephemeral=True)
            if decision is True: # has been unbanned
                return await inter.send(
                    embed = Embed(
                        title="Ban Lifted.",
                        description="You have been unbanned from AP Students! Welcome back :)\nJoin back using [this link!](https://discord.gg/apstudents)",
                        color=self.bot.colors["green"]
                    ),
                    ephemeral=True
                )
            if decision is False: # appeal was denied
                if time.time() - last_appeal_time < 60 * 60 * 24 * 7 * 2: # wait 12 weeks before appealing again.
                    return await inter.send("Your last appeal was denied. Please wait a while before appealing again.") 
        # if there is no known last_appeal_time, or last appeal deicion was false and 12 weeks have passed
        await inter.response.send_modal(BanAppealModal(self.bot))

class BanAppeal(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot
        self.bot.loop.create_task(self.create_views())

    async def create_views(self):
        await self.bot.wait_until_ready()
        if not self.bot.rolemenu_view_set:
            self.bot.add_view(BanAppealView(self.bot))
            self.bot.rolemenu_view_set = True

        pending_decisions = await self.bot.db.get_all_pending_decisions()

        for user_id, submission_time, message_id in pending_decisions.items():
            time_left: int = (submission_time+60*60*24*7*2) - time.time()
            if time_left < 0:
                await generic_decide(self.bot, user_id, message_id)
            else:
                self.bot.loop.call_later(
                    time_left,
                    asyncio.create_task,
                    generic_decide(self.bot, user_id, message_id)
                )


    @slash_command(name="appealbutton")
    @application_checks.is_owner()
    async def send_appeal_button(self, inter: Interaction):
        await inter.send(
            embed=Embed(
                title="Ban Appeal",
                description="To begin the appeal process, please click on the button below. Your appeal will be decided on after 2 weeks of submission. You must wait for a while before sending another appeal.",
                color=self.bot.colors["blue"]
            ),
            view=BanAppealView(self.bot)
        )



def setup(bot: APBot) -> None:
    bot.add_cog(BanAppeal(bot))
