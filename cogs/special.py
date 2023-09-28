from nextcord import Interaction, Member, SlashOption, slash_command
from nextcord.ext import commands

from bot_base import APBot


class SpecialPerms(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="esclude", description="Forbid a member ffrom viewing #emotional-support")
    async def _bonk(
        self,
        inter: Interaction,
        member: Member = SlashOption(name="member", description="Member to forbid access", required=True),
    ):
        if self.bot.config.get("special_perms_role_id") not in [i.id for i in inter.user.roles]:
            return await inter.send("You ain't allowed to use that command!", ephemeral=True)
        role = await self.bot.getch_role(self.bot.guild.id, self.bot.config.get("esclusion_role_id"))
        await member.add_roles(role)
        return await inter.send(f"Added Esclusion {role.mention} to {inter.user.mention}", ephemeral=True)

def setup(bot: APBot):
    bot.add_cog(SpecialPerms(bot))
