import asyncio
import datetime

from bot_base import APBot
from nextcord import Embed, Object
from nextcord.ext import commands, tasks


class Decay(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot
        self.decay.start()

    @tasks.loop(hours=24 * 7)
    async def decay(self):
        """
        Removes 1 infraction point per week of all members.
            - Runs a MongoDB command if it ought to decay.
        """

        # attempt to remove one inf point and get next decay date
        next_decay = await self.bot.db.remove_one_inf()

        if next_decay:  # removing one inf point was successful, got next decay date
            emb = Embed(
                title="Decay Success",
                description=f"Next decay at <t:{next_decay.timestamp()}:F> <t:{next_decay.timestamp()}:R>",
                color=self.bot.colors["green"],
            )
            content = ""
        else:  # failed removing one inf point, send error message instead
            emb = Embed(
                title="Decay Failure",
                description="Failed to decay. Please check logs and decay manuallly.",
                color=self.bot.colors["red"],
            )
            # mention bot staff role id if configured, or else 0
            content = f"<@&{self.bot.config.get('bot_staff_role_id', 0)}>"

        # get decay logs channel, or else get logs channel
        channel = await self.bot.getch_channel(self.bot.config.get("decay_logs_channel", self.bot.config.get("logs_channel")))
        await channel.send(embed=emb, content=content)

    @decay.before_loop
    async def decay_before_loop(self):
        await self.bot.wait_until_ready()

        # calculate time till next decay
        time_diff = (await self.bot.db.get_decay_date() - datetime.datetime.now()).total_seconds()
        if time_diff > 0:
            # sleep for duration if decay date has not passed
            await asyncio.sleep(time_diff)


async def setup(bot: APBot) -> None:
    await bot.add_cog(Decay(bot), guilds=[Object(id=bot.guild_id)])
