from __future__ import annotations

import traceback

import nextcord
from nextcord.ext import commands

from bot_base import APBot
from cogs.server_log.base import (
    ServerLogCog,
    clip,
    diff_permissions,
    format_permission_names,
)


def role_reference(role: nextcord.Role) -> str:
    return f"{role.mention}\n`{role.name}` (`{role.id}`)"


def color_hex(color) -> str:
    value = getattr(color, "value", None)

    if not value:
        return "`Default` (no color)"

    return f"`#{value:06X}`"


class RoleLog(ServerLogCog):
    """Role Create / Delete / Update logs."""

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: nextcord.Role) -> None:
        try:
            if role.id in self.ignored_role_ids():
                return

            entry = await self.audit(
                role.guild,
                nextcord.AuditLogAction.role_create,
                target_id=role.id,
            )

            embed = self.build_embed(
                "Role Created",
                color_name="green",
                fallback=0x2ECC71,
                description=f"Role **{role.name}** was created.",
            )
            embed.add_field(name="Role", value=role_reference(role), inline=True)
            embed.add_field(name="Color", value=color_hex(role.color), inline=True)
            embed.add_field(
                name="Displayed Separately",
                value="Yes" if role.hoist else "No",
                inline=True,
            )
            embed.add_field(
                name="Mentionable",
                value="Yes" if role.mentionable else "No",
                inline=True,
            )

            granted, _ = diff_permissions(nextcord.Permissions.none(), role.permissions)

            if granted:
                embed.add_field(
                    name="Permissions",
                    value=format_permission_names(granted),
                    inline=False,
                )

            self.add_actor(embed, entry, name="Created By")
            embed.set_footer(text=f"Role ID: {role.id}")

            await self.send_log(role.guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_guild_role_create failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: nextcord.Role) -> None:
        try:
            if role.id in self.ignored_role_ids():
                return

            entry = await self.audit(
                role.guild,
                nextcord.AuditLogAction.role_delete,
                target_id=role.id,
            )

            embed = self.build_embed(
                "Role Deleted",
                color_name="red",
                fallback=0xE74C3C,
                description=f"Role **{role.name}** was deleted.",
            )
            embed.add_field(name="Role Name", value=f"`{role.name}` (`{role.id}`)", inline=True)
            embed.add_field(name="Color", value=color_hex(role.color), inline=True)

            # Members are still attached to the cached role object at delete time.
            member_count = len(getattr(role, "members", []) or [])
            embed.add_field(name="Members With Role", value=f"`{member_count}`", inline=True)

            self.add_actor(embed, entry, name="Deleted By")
            embed.set_footer(text=f"Role ID: {role.id}")

            await self.send_log(role.guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_guild_role_delete failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: nextcord.Role, after: nextcord.Role) -> None:
        try:
            if after.id in self.ignored_role_ids():
                return

            changes: list[tuple[str, str, bool]] = []

            if before.name != after.name:
                changes.append(("Name", f"`{before.name}` → `{after.name}`", True))

            if before.color != after.color:
                changes.append(("Color", f"{color_hex(before.color)} → {color_hex(after.color)}", True))

            if before.hoist != after.hoist:
                changes.append((
                    "Displayed Separately",
                    f"`{'Yes' if before.hoist else 'No'}` → `{'Yes' if after.hoist else 'No'}`",
                    True,
                ))

            if before.mentionable != after.mentionable:
                changes.append((
                    "Mentionable",
                    f"`{'Yes' if before.mentionable else 'No'}` → `{'Yes' if after.mentionable else 'No'}`",
                    True,
                ))

            granted, revoked = diff_permissions(before.permissions, after.permissions)

            if granted:
                changes.append(("Permissions Granted", format_permission_names(granted), False))

            if revoked:
                changes.append(("Permissions Revoked", format_permission_names(revoked), False))

            # Position shuffles fire this event constantly and carry no useful
            # information on their own, so they are deliberately not logged.
            if not changes:
                return

            entry = await self.audit(
                after.guild,
                nextcord.AuditLogAction.role_update,
                target_id=after.id,
            )

            embed = self.build_embed(
                "Role Updated",
                color_name="yellow",
                fallback=0xF1C40F,
                description=f"Role {after.mention} was updated.",
            )
            embed.add_field(name="Role", value=f"`{after.name}` (`{after.id}`)", inline=False)

            for name, value, inline in changes:
                embed.add_field(name=name, value=clip(value), inline=inline)

            self.add_actor(embed, entry, name="Updated By")
            embed.set_footer(text=f"Role ID: {after.id}")

            await self.send_log(after.guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_guild_role_update failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()


def setup(bot: APBot) -> None:
    bot.add_cog(RoleLog(bot))
