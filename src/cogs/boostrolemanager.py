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

    async def cleanup_guild_nitro_roles(self, guild: nextcord.Guild):
        booster_role = nextcord.utils.get(guild.roles, name=self.booster_role_name)

        nitro_roles = [
            role for role in guild.roles
            if role.name in self.nitro_role_names
        ]

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

                has_booster_role = booster_role in member.roles if booster_role else False

                if has_booster_role:
                    continue

                roles_to_remove = [
                    role for role in member.roles
                    if role.name in self.nitro_role_names
                ]

                if not roles_to_remove:
                    continue

                try:
                    await member.remove_roles(
                        *roles_to_remove,
                        reason="User has nitro role(s) but is not currently boosting"
                    )
                    removed_count += 1
                    print(
                        f"[BoostTracker] Removed {[r.name for r in roles_to_remove]} "
                        f"from {member} ({member.id}) in {guild.name}"
                    )
                except Forbidden as e:
                    print(f"[BoostTracker] Missing permissions for {member}: {e}")
                except HTTPException as e:
                    print(f"[BoostTracker] HTTP error for {member}: {e}")

                await asyncio.sleep(0.1)

        print(f"[BoostTracker] Cleanup finished in {guild.name}. Removed roles from {removed_count} member(s).")

    @commands.Cog.listener()
    async def on_ready(self):
        if self.started_cleanup:
            return

        self.started_cleanup = True
        print("[BoostTracker] Bot ready. Starting nitro role cleanup...")

        for guild in self.bot.guilds:
            await self.cleanup_guild_nitro_roles(guild)

        print("[BoostTracker] Startup cleanup complete.")

    @commands.Cog.listener()
    async def on_member_update(self, before: nextcord.Member, after: nextcord.Member):
        booster_role = nextcord.utils.get(after.guild.roles, name=self.booster_role_name)
        if booster_role is None:
            return

        before_has_booster = booster_role in before.roles
        after_has_booster = booster_role in after.roles

        if before_has_booster and not after_has_booster:
            roles_to_remove = [
                role for role in after.roles
                if role.name in self.nitro_role_names
            ]

            if not roles_to_remove:
                return

            try:
                await after.remove_roles(
                    *roles_to_remove,
                    reason="User stopped boosting"
                )
                print(
                    f"[BoostTracker] Removed {[r.name for r in roles_to_remove]} "
                    f"from {after} ({after.id}) after boost ended"
                )
            except Forbidden as e:
                print(f"[BoostTracker] Missing permissions for {after}: {e}")
            except HTTPException as e:
                print(f"[BoostTracker] HTTP error for {after}: {e}")

    @commands.command(name="syncboostroles")
    @commands.has_permissions(administrator=True)
    async def syncboostroles(self, ctx):
        await ctx.send("Checking nitro roles now...")
        await self.cleanup_guild_nitro_roles(ctx.guild)
        await ctx.send("Done.")

def setup(bot):
    bot.add_cog(BoostTracker(bot))
