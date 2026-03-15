import nextcord
from nextcord.ext import commands
from nextcord import Forbidden, HTTPException
import asyncio


class BoostTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.roles_to_remove = [
            "nitro-a",
            "nitro-b",
            "nitro-c",
            "nitro-d",
            "nitro-e",
            "nitro-f"
        ]
        self.cleanup_task_started = False

    async def remove_nitro_roles_if_not_boosting(self, member: nextcord.Member):

        if member.premium_since is not None:
            return

        roles_found = []
        for role_name in self.roles_to_remove:
            role = nextcord.utils.get(member.guild.roles, name=role_name)
            if role is not None and role in member.roles:
                roles_found.append(role)

        if not roles_found:
            return

        try:
            await member.remove_roles(*roles_found, reason="User is no longer boosting the server")
            print(f"Removed nitro roles from {member} ({member.id})")
        except Forbidden as e:
            print(f"Insufficient permissions while removing roles from {member}: {e}")
        except HTTPException as e:
            print(f"HTTP request failed while removing roles from {member}: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        if self.cleanup_task_started:
            return

        self.cleanup_task_started = True
        print("BoostTracker is ready. Running startup boost-role cleanup...")

        for guild in self.bot.guilds:
            try:
                async for member in guild.fetch_members(limit=None):
                    await self.remove_nitro_roles_if_not_boosting(member)
                    await asyncio.sleep(0.2)  # small delay to avoid spamming requests
            except Exception as e:
                print(f"Failed to scan guild {guild.name} ({guild.id}): {e}")

        print("Startup boost-role cleanup finished.")

    @commands.Cog.listener()
    async def on_member_update(self, before: nextcord.Member, after: nextcord.Member):

        if before.premium_since == after.premium_since:
            return

        if before.premium_since is not None and after.premium_since is None:
            await self.remove_nitro_roles_if_not_boosting(after)


def setup(bot):
    bot.add_cog(BoostTracker(bot))
