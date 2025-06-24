import discord
from discord.ext import commands

class BoostTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if (before.premium_since is None) == (after.premium_since is None) or after.premium_since:
            return

        roles_to_remove = [
            "nitro-a",
            "nitro-b",
            "nitro-c",
            "nitro-d",
            "nitro-e",
            "nitro-f"
        ]

        for role_name in roles_to_remove:
            role = discord.utils.get(after.guild.roles, name=role_name)
            if role not in after.roles: continue
            await after.remove_roles(role)