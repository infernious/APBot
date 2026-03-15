import nextcord
from nextcord.ext import commands
from nextcord import Forbidden, HTTPException
import asyncio


class BoostTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.nitro_role_names = {
            "nitro-a",
            "nitro-b",
            "nitro-c",
            "nitro-d",
            "nitro-e",
            "nitro-f"
        }
        self.booster_role_name = "Nitro Booster"
        self.started_cleanup = False

    def get_booster_role(self, guild: nextcord.Guild):
        return nextcord.utils.get(guild.roles, name=self.booster_role_name)

    def get_nitro_roles_from_member(self, member: nextcord.Member):
        return [role for role in member.roles if role.name in self.nitro_role_names]

    async def enforce_member_nitro_roles(self, member: nextcord.Member, reason: str):
        booster_role = self.get_booster_role(member.guild)
        nitro_roles = self.get_nitro_roles_from_member(member)

        if not nitro_roles:
            return False

        has_booster_role = booster_role in member.roles if booster_role else False
        if has_booster_role:
            return False

        try:
            await member.remove_roles(*nitro_roles, reason=reason)
            print(
                f"[BoostTracker] Removed {[r.name for r in nitro_roles]} "
                f"from {member} ({member.id}) | Reason: {reason}"
            )
            return True
        except Forbidden as e:
            print(f"[BoostTracker] Missing permissions for {member}: {e}")
        except HTTPException as e:
            print(f"[BoostTracker] HTTP error for {member}: {e}")

        return False

    async def cleanup_guild_nitro_roles(self, guild: nextcord.Guild):
        nitro_roles = [role for role in guild.roles if role.name in self.nitro_role_names]

        if not nitro_roles:
            print(f"[BoostTracker] No nitro roles found in {guild.name}")
            return

        processed_members = set()
        removed_count = 0

        for nitro_role in nitro_roles:
            for member in nitro_role.members:
                if member.id in processed_members:
                    continue
                processed_members.add(member.id)

                removed = await self.enforce_member_nitro_roles(
                    member,
                    reason="Startup/manual nitro-role cleanup"
                )
                if removed:
                    removed_count += 1

                await asyncio.sleep(0.1)

        print(f"[BoostTracker] Cleanup finished in {guild.name}. Removed roles from {removed_count} member(s).")

    @commands.Cog.listener()
    async def on_ready(self):
        if self.started_cleanup:
            return

        self.started_cleanup = True
        print("[BoostTracker] Bot ready. Starting nitro cleanup...")

        for guild in self.bot.guilds:
            await self.cleanup_guild_nitro_roles(guild)

        print("[BoostTracker] Startup cleanup complete.")

    @commands.Cog.listener()
    async def on_member_update(self, before: nextcord.Member, after: nextcord.Member):
        before_role_ids = {role.id for role in before.roles}
        after_role_ids = {role.id for role in after.roles}


        if before_role_ids == after_role_ids:
            return

        await self.enforce_member_nitro_roles(
            after,
            reason="Member has nitro role(s) without Nitro Booster"
        )

    @commands.command(name="syncboostroles")
    @commands.has_permissions(administrator=True)
    async def syncboostroles(self, ctx):
        await ctx.send("Checking nitro roles now...")
        await self.cleanup_guild_nitro_roles(ctx.guild)
        await ctx.send("Done.")

def setup(bot):
    bot.add_cog(BoostTracker(bot))
