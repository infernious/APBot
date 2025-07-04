from nextcord import Interaction, Member, SlashOption, slash_command
from nextcord.ext import commands

from bot_base import APBot


class SpecialPerms(commands.Cog):
    def __init__(self, bot: APBot) -> None:
        self.bot = bot

    @slash_command(name="esclude", description="Forbid a member from viewing #emotional-support")
    async def _bonk(
        self,
        inter: Interaction,
        member: Member = SlashOption(name="member", description="Member to forbid access", required=True),
    ):
        # Allowed role names (lowercased for comparison)
        allowed_roles = {"special perms", "chat moderator", "admin"}
        exclusion_role_name = "ESclusion"  

        # Get all role names the user invoking the command has
        user_role_names = {role.name.lower() for role in inter.user.roles}

        # Check if user has permission
        if not allowed_roles & user_role_names:
            return await inter.send("You ain't allowed to use that command!", ephemeral=True)

        # Get the exclusion role object by name from the current guild
        guild = inter.guild
        if guild is None:
            return await inter.send("Guild not found.", ephemeral=True)

        role = next((r for r in guild.roles if r.name.lower() == exclusion_role_name.lower()), None)
        if not role:
            return await inter.send(f"Role '{exclusion_role_name}' not found in this server.", ephemeral=True)

        await member.add_roles(role)
        await inter.send(f"Added {role.mention} to {member.mention}", ephemeral=True)


def setup(bot: APBot):
    bot.add_cog(SpecialPerms(bot))
