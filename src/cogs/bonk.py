import asyncio
import time
from datetime import datetime as dt
from typing import List, Union
from uuid import uuid4

from nextcord import Embed, Interaction, SlashOption, slash_command
from nextcord.ext import commands

from bot_base import APBot
from cogs.utils import convert_time


class Bonk(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    async def remind(self, reminder_id: str, user_id: int, start_time: int, message: str) -> None:
        if reminder_id not in await self.bot.db.bonk.get_all_user_reminders(user_id):
            return

        await self.bot.db.bonk.remove(user_id, reminder_id)
        user = await self.bot.getch_user(user_id)

        if not user:
            return

        await user.send(f"Reminder! Set on <t:{start_time}:F> (<t:{start_time}:R>)\n{message or ''}")

    @slash_command(name="bonk", description="Bonks Stuff")
    async def _bonk(self, inter: Interaction):
        ...

    @_bonk.subcommand(name="set", description="Set a reminder!")
    async def _bonk_set(
        self,
        inter: Interaction,
        duration: str = SlashOption("duration", description="Reminder duration. Format: 5h9m2s", required=True),
        message: str = SlashOption("message", description="Reminder message.", required=False, default=""),
    ) -> None:
        if len(await self.bot.db.bonk.get_all_user_reminders(inter.user.id)) >= 25:
            return await inter.send("You can't have more than 25 reminders at once!")

        duration: Union[str, int] = convert_time(duration)
        if isinstance(duration, str):
            return await inter.send(duration, ephemeral=True)

        if duration > 60 * 60 * 24 * 7 * 52 * 4:
            return await inter.send("You can't set a reminder for more than 4 years!", ephemeral=True)

        start_time = int(time.time())
        end_time = start_time + duration

        reminder_id = uuid4().hex
        await self.bot.db.bonk.new(reminder_id, inter.user.id, start_time, end_time, message)

        self.bot.loop.call_later(
            duration,
            asyncio.create_task,
            self.remind(reminder_id, inter.user.id, start_time, message),
        )

        m = f"about `{message}` " if message else ""
        await inter.response.send_message(f"I'll remind you {m}on <t:{int(end_time)}:F>", ephemeral=True)

    @_bonk.subcommand(name="list", description="List all your reminders")
    async def _bonk_list(self, inter: Interaction) -> None:
        user_reminders = (await self.bot.db.bonk.get_all_user_reminders(inter.user.id)).values()
        if len(user_reminders) == 0:
            return await inter.response.send_message("You have no set reminders!", ephemeral=True)

        formatted_reminders: List[str] = []
        for ind, reminder in enumerate(user_reminders):
            prefix = f"{ind}. "
            time_str = f"Reminder <t:{int(reminder['end_time'])}:R>" + " - "
            reminder_message = reminder["message"] or ""
            avail_chars = 50 - len(prefix) - len(time_str)
            if len(reminder_message) > avail_chars:
                message = reminder_message[avail_chars - 3] + "..."
            else:
                message = reminder_message or "No Message"
            formatted_reminders.append(prefix + time_str + message)

        await inter.response.send_message(
            embed=Embed(
                title="Your Reminders",
                description="\n".join(formatted_reminders),
            ),
            ephemeral=True,
        )

    @_bonk.subcommand(name="remove", description="Remove a specific reminder!")
    async def _bonk_remove(
        self,
        inter: Interaction,
        reminder: str = SlashOption(
            name="reminder",
            description="Which reminder to remove.",
        ),
    ):
        await self.bot.db.bonk.remove(inter.user.id, reminder)
        await inter.response.send_message("Removed reminder.", ephemeral=True)

    @_bonk_remove.on_autocomplete("reminder")
    async def _bonk_remve_autocomplete(self, inter: Interaction, reminder_id: str):
        formatted_choices = {}
        user_reminders = await self.bot.db.bonk.get_all_user_reminders(inter.user.id)

        for ind, (reminder_id, reminder_details) in enumerate(user_reminders.items()):
            prefix: str = f"{ind+1}. "
            time_str: str = "Reminder at " + dt.fromtimestamp(reminder_details["end_time"]).strftime("%m %b %Y %H:%M:%S") + " - "
            reminder_message = reminder_details["message"] or ""
            avail_chars = 100 - len(prefix) - len(time_str)
            if len(reminder_message) > avail_chars:
                message: str = reminder_message[: avail_chars - 3] + "..."
            else:
                message: str = reminder_message or "No Message"
            formatted_choices[prefix + time_str + message] = reminder_id
        await inter.response.send_autocomplete(formatted_choices)

    @_bonk.subcommand(name="purge", description="Remove all reminders")
    async def _bonk_purge(self, inter: Interaction):
        await self.bot.db.bonk.remove_all_user_reminders(inter.user.id)
        await inter.send("Removed all reminders!", ephemeral=True)

    @commands.Cog.listener("on_ready")
    async def _bonk_on_ready(self) -> None:
        bonks = await self.bot.db.bonk.get_all()

        for reminder_id, reminder_details in bonks.items():
            time_left: int = reminder_details["end_time"] - time.time()
            if time_left < 0:
                await self.remind(
                    reminder_id, reminder_details["user_id"], reminder_details["start_time"], reminder_details["message"]
                )
            else:
                self.bot.loop.call_later(
                    time_left,
                    asyncio.create_task,
                    self.remind(
                        reminder_id, reminder_details["user_id"], reminder_details["start_time"], reminder_details["message"]
                    ),
                )


def setup(bot: APBot):
    bot.add_cog(Bonk(bot))