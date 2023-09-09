from nextcord import Embed, Message, Object, errors
from nextcord.ext import commands, tasks
from typing import Optional

from bot_base import APBot


class BanAppeal(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot
        self.appeal_loop.start()

    @tasks.loop(hours=24)
    async def appeal_loop(self):
        """
        Checks every day for ban appeals.
        """
        appeals = await self.bot.db.get_appeals()
        for user_id, message_id in appeals.items():
            appeal_message: Optional[Message] = await self.bot.getch_message(self.bot.config.get("appeals_channel_id"), message_id)
            if not appeal_message or not appeal_message.reactions:
                continue

            maintain_ban_reactions = len([i for i in appeal_message.reactions if i.emoji == "🔴"])
            unban_reactions = len([i for i in appeal_message.reactions if i.emoji == "🟢"])

            decision_embed = Embed(title="")

            if unban_reactions > maintain_ban_reactions:
                try:
                    decision_embed.colour = self.bot.colors["green"]
                    decision_embed.add_field(name="", value="Member will be unbanned!")
                    await self.bot.guild.unban(Object(id=user_id))
                except errors.NotFound:
                    decision_embed.colour = self.bot.colors["orange"]
                    decision_embed.add_field(name="", value="Member is already unbanned!")
                try:
                    user = await self.bot.getch_user(user_id)
                    await user.send(embed=Embed(title="Ban Lifted.", description="You have been unbanned from AP Students! Welcome back :)\nJoin back using [this](https://discord.gg/apstudents) link!", color=self.bot.colors["green"]))
                except:
                    pass
            else:
                decision_embed.colour = self.bot.colors["red"]
                decision_embed.add_field(name="", value="Member will remain banned!")

            await appeal_message.thread.send(embed=decision_embed)
            await appeal_message.thread.edit(archived=True)

            await self.bot.db.remove_pending_appeal(user_id)

    @appeal_loop.before_loop
    async def appeal_before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: APBot) -> None:
    await bot.add_cog(BanAppeal(bot), guilds=[Object(id=bot.guild_id)])
