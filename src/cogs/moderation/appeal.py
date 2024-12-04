import nextcord
from nextcord.ext import tasks, commands

import datetime

yellow = 0xffff00
orange = 0xffa500
light_orange = 0xffa07a
dark_orange = 0xff5733
red = 0xff0000
green = 0x00ff00


class BanAppeal(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.appeal_loop.start()

    @tasks.loop(hours=24)
    async def appeal_loop(self):

        """
        Checks every day for ban appeals.
        """

        guild = self.bot.get_guild(self.bot.guild_id)
        channel = nextcord.utils.get(guild.channels, name="important-updates")
        cursor = self.bot.user_config.find({"check_appeal_date": {"$lte": datetime.datetime.now()}})
        documents = await cursor.to_list(length=100)

        for document in documents:

            appeal_message = await channel.fetch_message(document["appeal_message_id"])

            maintain_ban_reaction = nextcord.utils.get(appeal_message.reactions, emoji="🔴")
            unban_reaction = nextcord.utils.get(appeal_message.reactions, emoji="🟢")

            thread = nextcord.utils.find(lambda c: f"({document['user_id']})" in c.name, appeal_message.channel.threads)
            decision_embed = nextcord.Embed(title='')

            if unban_reaction.count > maintain_ban_reaction.count:
                try:
                    decision_embed.colour = green
                    decision_embed.add_field(name="", value="Member will be unbanned!")
                    await thread.send(embed=decision_embed)
                    await guild.unban(nextcord.Object(id=document["user_id"]))
                except nextcord.errors.NotFound:
                    decision_embed.colour = orange
                    decision_embed.add_field(name="", value="Member is already unbanned!")
            else:
                decision_embed.colour = red
                decision_embed.add_field(name="", value="Member will remain banned!")

            await thread.edit(archived=True)
            await self.bot.user_config.update_one({"_id": document["_id"]}, {"$unset": {"check_appeal_date": ""}})
            await self.bot.user_config.update_one({"_id": document["_id"]}, {"$unset": {"appeal_message_id": ""}})

    @appeal_loop.before_loop
    async def appeal_before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BanAppeal(bot), guilds=[nextcord.Object(id=bot.guild_id)])