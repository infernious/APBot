import datetime


from discord import Message, Embed, Object, errors, utils
from discord.ext import commands, tasks

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

        guild = self.bot.get_guild(self.bot.guild_id)
        channel = utils.get(guild.channels, name="important-updates")
        cursor = self.bot.user_config.find({"check_appeal_date": {"$lte": datetime.datetime.now()}})
        documents = await cursor.to_list(length=100)

        for document in documents:
            appeal_message: Message = await self.bot.getch_message(channel.id, document["appeal_message_id"])

            if not appeal_message or not appeal_message.reactions:
                continue

            # This is not the best way to do it, but it ensures the variables are always defined, and it's pretty elegant.
            maintain_ban_reactions = len([i for i in appeal_message.reactions if i.emoji == "🔴"])
            unban_reactions = len([i for i in appeal_message.reactions if i.emoji == "🟢"])

            thread = utils.find(lambda c: f"({document['user_id']})" in c.name, appeal_message.channel.threads)
            decision_embed = Embed(title="")

            if unban_reactions > maintain_ban_reactions:
                try:
                    decision_embed.colour = self.bot.colors["green"]
                    decision_embed.add_field(name="", value="Member will be unbanned!")
                    await guild.unban(Object(id=document["user_id"]))
                except errors.NotFound:
                    decision_embed.colour = self.bot.colors["orange"]
                    decision_embed.add_field(name="", value="Member is already unbanned!")
            else:
                decision_embed.colour = self.bot.colors["red"]
                decision_embed.add_field(name="", value="Member will remain banned!")

            await thread.send(embed=decision_embed)
            await thread.edit(archived=True)

            await self.bot.user_config.update_one({"_id": document["_id"]}, {"$unset": {"check_appeal_date": ""}})
            await self.bot.user_config.update_one({"_id": document["_id"]}, {"$unset": {"appeal_message_id": ""}})

    @appeal_loop.before_loop
    async def appeal_before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: APBot) -> None:
    await bot.add_cog(BanAppeal(bot), guilds=[Object(id=bot.guild_id)])
