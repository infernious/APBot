import datetime

from discord import Embed, Object, utils
from discord.ext import commands, tasks

from bot_base import APBot


class Decay(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: APBot = bot
        self.decay.start()

    @tasks.loop(hours=24)
    async def decay(self):
        """
        Removed 1 infraction point per week of all members.
            - Checks daily if decay should be done by comparing current date to next decay date.
            - Runs a MongoDB command if it ought to decay.
        """

        current_time = datetime.datetime.now()
        config = await self.bot.read_user_config(self.bot.application_id)

        decay_embed = Embed(title="")

        if config["decay_day"] <= current_time:
            await self.bot.user_config.update_many({"infraction_points": {"$gt": 0}}, {"$inc": {"infraction_points": -1}})
            config["decay_day"] = config["decay_day"] + datetime.timedelta(days=7)

            decay_embed.color = self.bot.colors["green"]
            decay_embed.add_field(
                name="Decay Status: True",
                value=f"Next decay at {utils.format_dt(config['decay_day'], style='F')} {utils.format_dt(config['decay_day'], style='R')}.",
            )
        else:
            decay_embed.color = self.bot.colors["red"]
            decay_embed.add_field(
                name="Decay Status: False",
                value=f"Next decay at {utils.format_dt(config['decay_day'], style='F')} {utils.format_dt(config['decay_day'], style='R')}.",
            )

        await self.bot.update_user_config(self.bot.application_id, config)
        logs = await self.bot.getch_channel(self.bot.config.get("log_channel"))
        await logs.send(embed=decay_embed)

    @decay.before_loop
    async def decay_before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: APBot) -> None:
    await bot.add_cog(Decay(bot), guilds=[Object(id=bot.guild_id)])
