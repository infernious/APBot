import nextcord
from nextcord.ext import commands
from bot_base import APBot

HELPER_ROLE_NAMES = {"Helper (Click on their names!)"}

HELPER_DM_MESSAGE = """Hi there!

Thanks for signing up to be a Helper <:pikaheart:357317554600935424>. To make your experience as smooth as possible, we’re here to help and make sure that you get treated fairly. Below are all instances that you can report to <@1464966749643341847>, and we’ll take care of it from our end.

- Unsolicited pinging
- Unsolicited DM’ing
- Rude behavior
- Disruptive behavior that interferes with helping
- Getting pinged by /question when the user hasn’t waited 10 minutes

When reporting, please make sure to include the user’s discord handle and a screenshot if possible.

Thank you! As always, feel free to send suggestions & feedback about the Helper system to <@1464966749643341847>."""


class HelperDMCog(commands.Cog):
    def __init__(self, bot: APBot):
        self.bot = bot

    def gained_helper_role(self, before, after) -> bool:
        before_role_ids = {role.id for role in before.roles}

        for role in after.roles:
            if role.id not in before_role_ids and role.name in HELPER_ROLE_NAMES:
                return True

        return False

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if getattr(after, "bot", False):
            return

        if not self.gained_helper_role(before, after):
            return

        try:
            await after.send(HELPER_DM_MESSAGE)
        except (nextcord.Forbidden, nextcord.HTTPException):
            pass


def setup(bot: APBot):
    bot.add_cog(HelperDMCog(bot))
