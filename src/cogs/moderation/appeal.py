from nextcord import Embed, Message, Object, errors, ui, TextInputStyle, Interaction, ButtonStyle, slash_command
from nextcord.ext import commands, application_checks
from typing import Optional

from bot_base import APBot
import asyncio
from datetime import datetime, timedelta
import time

REVIEW_DELAY_SECONDS = 60 * 60 * 24 * 14  # 2 weeks
REAPPEAL_DELAY_SECONDS = 60 * 60 * 24 * 84  # 12 weeks


async def generic_decide(bot: APBot, user_id: int, message_id: int):
    appeal_message: Optional[Message] = await bot.getch_message(bot.config.get("appeals_channel_id"), message_id)

    maintain_ban_reactions = 0
    unban_reactions = 0

    for reaction in appeal_message.reactions:
        if str(reaction.emoji) == "🟢":
            unban_reactions = reaction.count
        elif str(reaction.emoji) == "🔴":
            maintain_ban_reactions = reaction.count

    decision_embed = Embed(title="")
    user = await bot.getch_user(user_id)
    appeal_result = None

    main_guild = bot.get_guild(int(bot.config.get("guild_id")))
    if not main_guild:
        print("⚠️ Failed to fetch main guild. Cannot process appeal.")
        return

    if unban_reactions > maintain_ban_reactions:
        try:
            await main_guild.unban(Object(id=user_id))
            decision_embed.color = bot.colors["green"]
            decision_embed.add_field(name="", value="Member will be unbanned!")
            appeal_result = True
        except errors.NotFound:
            decision_embed.color = bot.colors["orange"]
            decision_embed.add_field(name="", value="Member is already unbanned!")
        try:
            await user.send(
                embed=Embed(
                    title="Ban Lifted.",
                    description="You have been unbanned from AP Students! Welcome back :)",
                    color=bot.colors["green"],
                )
            )
        except:
            pass
    else:
        decision_embed.color = bot.colors["red"]
        decision_embed.add_field(name="", value="Member will remain banned.")
        appeal_result = False
        try:
            await user.send(
                embed=Embed(
                    title="Ban Appeal Denied.",
                    description=f"Your appeal was reviewed and denied. You may appeal again after 12 weeks.",
                    color=bot.colors["red"],
                )
            )
        except:
            pass

    await appeal_message.thread.send(embed=decision_embed)
    await appeal_message.thread.edit(archived=True)

    await bot.db.appeal.set_last_appeal(user_id, time.time(), appeal_result)


class BanAppealModal(ui.Modal):
    def __init__(self, bot: APBot):
        self.bot = bot
        super().__init__(title="Ban Appeal", custom_id="appeal_modal", timeout=None)

        self.appeal = ui.TextInput(
            label="Ban Appeal",
            style=TextInputStyle.paragraph,
            custom_id="appeal_modal_why",
            min_length=100,
            max_length=750,
            required=True,
            placeholder="Why should your ban be appealed? We recommend taking a few weeks to write a thoughtful response.",
        )
        self.add_item(self.appeal)

        self.media = ui.TextInput(
            label="Supporting Media",
            required=False,
            placeholder="Feel free to send links to supporting media here.",
            style=TextInputStyle.paragraph,
            custom_id="appeal_modal_media",
            max_length=150,
        )
        self.add_item(self.media)

        self.miscellaneous = ui.TextInput(
            label="Anything else?",
            required=False,
            placeholder="If there is anything else you would like to share, please do so below.",
            style=TextInputStyle.paragraph,
            custom_id="appeal_modal_misc",
            max_length=750,
        )
        self.add_item(self.miscellaneous)

    async def callback(self, inter: Interaction):
        await inter.response.defer(ephemeral=True, with_message=True)

        try:
            await self.bot.guild.fetch_member(inter.user.id)
            return await inter.followup.send("You are not banned from the main server.", ephemeral=True)
        except errors.NotFound:
            pass

        ch = await self.bot.getch_channel(self.bot.config.get("appeals_channel_id"))
        now = datetime.now()

        emb = Embed(title="Ban Appeal", color=self.bot.colors["light_orange"], timestamp=now)
        emb.add_field(name="User Info", value=f"User: {inter.user}\nID: {inter.user.id}", inline=False)
        emb.add_field(name="Ban Appeal", value=f"```\n{self.appeal.value.strip()}\n```", inline=False)

        if self.media.value.strip():
            emb.add_field(name="Supporting Media", value=f"```\n{self.media.value.strip()}\n```", inline=False)
        if self.miscellaneous.value.strip():
            emb.add_field(name="Additional Information", value=f"```\n{self.miscellaneous.value.strip()}\n```", inline=False)

        appeal_message: Message = await ch.send(embed=emb)
        await appeal_message.add_reaction("🟢")
        await appeal_message.add_reaction("🟡")
        await appeal_message.add_reaction("🔴")
        await appeal_message.create_thread(name=f"{now.strftime('%m/%d/%Y')} - {inter.user.name}")

        await self.bot.db.appeal.reset_appeal_state(inter.user.id, now.timestamp(), appeal_message.id)

        self.bot.loop.call_later(
            REVIEW_DELAY_SECONDS,
            asyncio.create_task,
            generic_decide(self.bot, inter.user.id, appeal_message.id)
        )

        await inter.followup.send("Your appeal has been sent. You will receive a response in 2 weeks.", ephemeral=True)


class BanAppealView(ui.View):
    def __init__(self, bot: APBot):
        self.bot = bot
        super().__init__(timeout=None)

    @ui.button(label="Appeal Ban", style=ButtonStyle.blurple, custom_id="appeal")
    async def callback(self, button: ui.Button, inter: Interaction):
        main_guild = self.bot.guild
        try:
            await main_guild.fetch_member(inter.user.id)
            return await inter.send("You are not banned from the main server.", ephemeral=True)
        except errors.NotFound:
            pass

        now = time.time()
        last_appeal_time, decision = await self.bot.db.appeal.get_last_appeal(inter.user.id)

        # Check for pending appeal
        pending_entry = await self.bot.db.appeal.get_pending_decision(inter.user.id)
        if pending_entry:
            channel = await self.bot.getch_channel(self.bot.config.get("appeals_channel_id"))
            try:
                await channel.fetch_message(pending_entry["message_id"])
                return await inter.send("Your last appeal is still being considered.", ephemeral=True)
            except errors.NotFound:
                await self.bot.db.appeal.clear_last_appeal(inter.user.id)

        if last_appeal_time and decision is False:
            time_since_last = now - last_appeal_time
            if time_since_last < REAPPEAL_DELAY_SECONDS:
                seconds_left = int(REAPPEAL_DELAY_SECONDS - time_since_last)
                days, seconds = divmod(seconds_left, 86400)
                hours, seconds = divmod(seconds, 3600)
                minutes, seconds = divmod(seconds, 60)
                return await inter.send(
                    f"Your appeal was reviewed and denied. You may appeal again after {days} day(s), {hours} hour(s), {minutes} minute(s), {seconds} second(s).",
                    ephemeral=True
                )

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

        pending_decisions = await self.bot.db.appeal.get_pending_decisions()

        for user_id, (submission_time, message_id) in pending_decisions.items():
            time_left = (submission_time + REVIEW_DELAY_SECONDS) - time.time()
            if time_left < 0:
                await generic_decide(self.bot, user_id, message_id)
            else:
                self.bot.loop.call_later(time_left, asyncio.create_task, generic_decide(self.bot, user_id, message_id))

    @slash_command(name="appealbutton", default_member_permissions=0x8)  # Admin only
    async def send_appeal_button(self, inter: Interaction):
        if inter.guild.id not in [
            int(self.bot.config.get("guild_id")),
            int(self.bot.config.get("ban_appeal_server"))
        ]:
            return await inter.send("This command can't be used in this server.", ephemeral=True)

        await inter.send(
            embed=Embed(
                title="Ban Appeal",
                description="To begin the appeal process, please click on the button below. Your appeal will be decided after 2 weeks of submission. You must wait before sending another appeal if denied.",
                color=self.bot.colors["blue"],
            ),
            view=BanAppealView(self.bot),
        )


def setup(bot: APBot) -> None:
    bot.add_cog(BanAppeal(bot))
