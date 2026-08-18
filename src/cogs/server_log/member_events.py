from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime, timezone
from typing import Optional

import nextcord
from nextcord.ext import commands

from bot_base import APBot
from cogs.server_log.base import (
    ServerLogCog,
    audit_touched,
    clip,
    format_role_list,
    format_timestamp,
    format_user,
)


# Accounts younger than this are flagged on join as a possible raid/alt signal.
NEW_ACCOUNT_THRESHOLD_DAYS = 7

# A ban fires both member_remove and member_ban, and the gateway does not
# guarantee an order. member_remove waits this long for a ban to show up so the
# same event is not logged twice.
BAN_GRACE_SECONDS = 2.0
BAN_MEMORY_SECONDS = 30.0


def humanize_delta(seconds: float) -> str:
    """Renders a duration as a short `2d 3h 15m` style string."""
    seconds = int(max(0, seconds))

    if seconds < 60:
        return f"{seconds}s"

    units = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
    parts: list[str] = []

    for label, size in units:
        if seconds >= size:
            value, seconds = divmod(seconds, size)
            parts.append(f"{value}{label}")

        if len(parts) == 2:
            break

    return " ".join(parts) if parts else "0s"


class MemberLog(ServerLogCog):
    """Member Join / Leave / Kick / Ban / Unban / Timeout / Role / Nickname logs."""

    def __init__(self, bot: APBot) -> None:
        super().__init__(bot)

        # member_id -> task that announces a timeout expiring on its own.
        self._timeout_tasks: dict[int, asyncio.Task] = {}

        # member_id -> monotonic time of a ban, so member_remove can stay quiet.
        self._recent_bans: dict[int, float] = {}

    def _remember_ban(self, member_id: Optional[int]) -> None:
        if member_id is None:
            return

        now = time.monotonic()
        self._recent_bans[member_id] = now
        self._recent_bans = {
            key: stamp
            for key, stamp in self._recent_bans.items()
            if now - stamp < BAN_MEMORY_SECONDS
        }

    def _was_recently_banned(self, member_id: int) -> bool:
        stamp = self._recent_bans.get(member_id)
        return stamp is not None and (time.monotonic() - stamp) < BAN_MEMORY_SECONDS

    def cog_unload(self) -> None:
        for task in list(self._timeout_tasks.values()):
            task.cancel()

        self._timeout_tasks.clear()

    # ------------------------------------------------------------------
    # Timeout expiry scheduling
    # ------------------------------------------------------------------

    def _cancel_timeout_task(self, member_id: int) -> None:
        task = self._timeout_tasks.pop(member_id, None)

        if task is not None:
            task.cancel()

    def _schedule_timeout_expiry(self, member, until: datetime) -> None:
        """
        Discord does not emit an event when a timeout runs out, so we wait it out
        ourselves. Tasks are rebuilt on_ready, so a restart only loses expiries
        that would have fired while the bot was down.
        """
        self._cancel_timeout_task(member.id)

        delay = (until - datetime.now(timezone.utc)).total_seconds()

        if delay <= 0:
            return

        self._timeout_tasks[member.id] = asyncio.create_task(
            self._announce_timeout_expiry(member.guild, member.id, delay)
        )

    async def _announce_timeout_expiry(self, guild, member_id: int, delay: float) -> None:
        try:
            await asyncio.sleep(delay)

            member = guild.get_member(member_id) if hasattr(guild, "get_member") else None

            if member is None:
                return

            # A new or extended timeout replaced the one we were waiting on.
            still_timed_out = getattr(member, "communication_disabled_until", None)

            if still_timed_out is not None and still_timed_out > datetime.now(timezone.utc):
                return

            embed = self.build_embed(
                "Member Timeout Expired",
                color_name="green",
                fallback=0x2ECC71,
                description=f"{member.mention}'s timeout ran out.",
            )
            self.set_author(embed, member)
            embed.add_field(name="Member", value=format_user(member), inline=True)
            embed.set_footer(text=f"Member ID: {member_id}")

            await self.send_log(guild, embed)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[ServerLog] Timeout expiry announcement failed: {type(exc).__name__}: {exc}")
        finally:
            self._timeout_tasks.pop(member_id, None)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Re-arms expiry announcements for timeouts that survived a restart."""
        guild = self.target_guild()

        if guild is None:
            return

        now = datetime.now(timezone.utc)

        for member in getattr(guild, "members", []) or []:
            until = getattr(member, "communication_disabled_until", None)

            if until is not None and until > now and member.id not in self._timeout_tasks:
                self._schedule_timeout_expiry(member, until)

    # ------------------------------------------------------------------
    # Join / Leave / Kick
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: nextcord.Member) -> None:
        try:
            created_at = getattr(member, "created_at", None)

            embed = self.build_embed(
                "Member Joined",
                color_name="green",
                fallback=0x2ECC71,
                description=f"{member.mention} joined the server.",
            )
            self.set_author(embed, member)
            embed.add_field(name="Member", value=format_user(member), inline=True)
            embed.add_field(name="Account Created", value=format_timestamp(created_at), inline=True)

            if created_at is not None:
                age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()

                if age_seconds < NEW_ACCOUNT_THRESHOLD_DAYS * 86400:
                    embed.add_field(
                        name="⚠️ New Account",
                        value=f"Created {humanize_delta(age_seconds)} ago.",
                        inline=False,
                    )

            member_count = getattr(member.guild, "member_count", None)

            if member_count is not None:
                embed.add_field(name="Member Count", value=f"`{member_count}`", inline=True)

            if getattr(member, "bot", False):
                entry = await self.audit(
                    member.guild,
                    nextcord.AuditLogAction.bot_add,
                    target_id=member.id,
                )
                self.add_actor(embed, entry, name="Added By")

            embed.set_footer(text=f"Member ID: {member.id}")

            await self.send_log(member.guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_member_join failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_member_remove(self, member: nextcord.Member) -> None:
        try:
            guild = member.guild

            # A ban also fires member_remove; on_member_ban owns that case.
            # Wait out the gateway ordering, then fall back to the audit log in
            # case the ban event never arrived.
            await asyncio.sleep(BAN_GRACE_SECONDS)

            if self._was_recently_banned(member.id):
                return

            ban_entry = await self.audit(
                guild,
                nextcord.AuditLogAction.ban,
                target_id=member.id,
                within=BAN_MEMORY_SECONDS,
                attempts=1,
            )

            if ban_entry is not None:
                return

            kick_entry = await self.audit(
                guild,
                nextcord.AuditLogAction.kick,
                target_id=member.id,
                within=10,
            )

            was_kicked = kick_entry is not None

            embed = self.build_embed(
                "Member Kicked" if was_kicked else "Member Left",
                color_name="red" if was_kicked else "orange",
                fallback=0xE74C3C if was_kicked else 0xE67E22,
                description=(
                    f"{member.mention} was kicked from the server."
                    if was_kicked
                    else f"{member.mention} left the server."
                ),
            )
            self.set_author(embed, member)
            embed.add_field(name="Member", value=format_user(member), inline=True)

            joined_at = getattr(member, "joined_at", None)
            embed.add_field(name="Joined", value=format_timestamp(joined_at), inline=True)

            if joined_at is not None:
                embed.add_field(
                    name="Time in Server",
                    value=f"`{humanize_delta((datetime.now(timezone.utc) - joined_at).total_seconds())}`",
                    inline=True,
                )

            embed.add_field(
                name="Roles Held",
                value=format_role_list(getattr(member, "roles", []) or []),
                inline=False,
            )

            if was_kicked:
                self.add_actor(embed, kick_entry, name="Kicked By")

            member_count = getattr(guild, "member_count", None)

            if member_count is not None:
                embed.add_field(name="Member Count", value=f"`{member_count}`", inline=True)

            embed.set_footer(text=f"Member ID: {member.id}")

            await self.send_log(guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_member_remove failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Ban / Unban
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_ban(self, guild: nextcord.Guild, user) -> None:
        try:
            self._remember_ban(getattr(user, "id", None))

            entry = await self.audit(
                guild,
                nextcord.AuditLogAction.ban,
                target_id=getattr(user, "id", None),
            )

            embed = self.build_embed(
                "Member Banned",
                color_name="red",
                fallback=0xE74C3C,
                description=f"{getattr(user, 'mention', user)} was banned from the server.",
            )
            self.set_author(embed, user)
            embed.add_field(name="Member", value=format_user(user), inline=True)

            # on_member_ban hands back a User for uncached members, so roles are
            # only available when the member was still in cache.
            roles = getattr(user, "roles", None)

            if roles:
                embed.add_field(name="Roles Held", value=format_role_list(roles), inline=False)

            self.add_actor(embed, entry, name="Banned By")
            embed.set_footer(text=f"Member ID: {getattr(user, 'id', 'unknown')}")

            await self.send_log(guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_member_ban failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_member_unban(self, guild: nextcord.Guild, user) -> None:
        try:
            entry = await self.audit(
                guild,
                nextcord.AuditLogAction.unban,
                target_id=getattr(user, "id", None),
            )

            embed = self.build_embed(
                "Member Unbanned",
                color_name="green",
                fallback=0x2ECC71,
                description=f"{getattr(user, 'mention', user)} was unbanned.",
            )
            self.set_author(embed, user)
            embed.add_field(name="Member", value=format_user(user), inline=True)
            self.add_actor(embed, entry, name="Unbanned By")
            embed.set_footer(text=f"Member ID: {getattr(user, 'id', 'unknown')}")

            await self.send_log(guild, embed)

        except Exception as exc:
            print(f"[ServerLog] on_member_unban failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Roles / Timeout / Nickname
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_update(self, before: nextcord.Member, after: nextcord.Member) -> None:
        try:
            await self._log_role_changes(before, after)
            await self._log_timeout_change(before, after)
            await self._log_nickname_change(before, after)

        except Exception as exc:
            print(f"[ServerLog] on_member_update failed: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    async def _log_role_changes(self, before: nextcord.Member, after: nextcord.Member) -> None:
        ignored = self.ignored_role_ids()

        before_roles = {role.id: role for role in getattr(before, "roles", []) or []}
        after_roles = {role.id: role for role in getattr(after, "roles", []) or []}

        added = [role for role_id, role in after_roles.items() if role_id not in before_roles and role_id not in ignored]
        removed = [role for role_id, role in before_roles.items() if role_id not in after_roles and role_id not in ignored]

        if not added and not removed:
            return

        entry = await self.audit(
            after.guild,
            nextcord.AuditLogAction.member_role_update,
            target_id=after.id,
        )

        if added:
            embed = self.build_embed(
                "Member Role Added",
                color_name="green",
                fallback=0x2ECC71,
                description=f"{after.mention} was given {len(added)} role(s).",
            )
            self.set_author(embed, after)
            embed.add_field(name="Member", value=format_user(after), inline=True)
            embed.add_field(name="Roles Added", value=format_role_list(added), inline=False)
            self.add_actor(embed, entry, name="Added By")
            embed.set_footer(text=f"Member ID: {after.id}")

            await self.send_log(after.guild, embed)

        if removed:
            embed = self.build_embed(
                "Member Role Removed",
                color_name="orange",
                fallback=0xE67E22,
                description=f"{after.mention} had {len(removed)} role(s) removed.",
            )
            self.set_author(embed, after)
            embed.add_field(name="Member", value=format_user(after), inline=True)
            embed.add_field(name="Roles Removed", value=format_role_list(removed), inline=False)
            self.add_actor(embed, entry, name="Removed By")
            embed.set_footer(text=f"Member ID: {after.id}")

            await self.send_log(after.guild, embed)

    async def _log_timeout_change(self, before: nextcord.Member, after: nextcord.Member) -> None:
        before_until: Optional[datetime] = getattr(before, "communication_disabled_until", None)
        after_until: Optional[datetime] = getattr(after, "communication_disabled_until", None)

        if before_until == after_until:
            return

        now = datetime.now(timezone.utc)
        entry = await self.audit(
            after.guild,
            nextcord.AuditLogAction.member_update,
            target_id=after.id,
            check=lambda candidate: audit_touched(candidate, "communication_disabled_until"),
        )

        if after_until is not None and after_until > now:
            was_active = before_until is not None and before_until > now

            embed = self.build_embed(
                "Member Timeout Updated" if was_active else "Member Timed Out",
                color_name="orange",
                fallback=0xE67E22,
                description=f"{after.mention} is timed out.",
            )
            self.set_author(embed, after)
            embed.add_field(name="Member", value=format_user(after), inline=True)
            embed.add_field(name="Expires", value=format_timestamp(after_until), inline=True)
            embed.add_field(
                name="Duration",
                value=f"`{humanize_delta((after_until - now).total_seconds())}`",
                inline=True,
            )
            self.add_actor(embed, entry, name="Timed Out By")
            embed.set_footer(text=f"Member ID: {after.id}")

            await self.send_log(after.guild, embed)
            self._schedule_timeout_expiry(after, after_until)
            return

        # Timeout cleared. A natural expiry is announced by the scheduled task,
        # so only report this when a moderator actually removed it.
        if before_until is not None and before_until > now:
            self._cancel_timeout_task(after.id)

            actor = getattr(entry, "user", None) if entry is not None else None

            if actor is None:
                return

            embed = self.build_embed(
                "Member Timeout Removed",
                color_name="green",
                fallback=0x2ECC71,
                description=f"{after.mention}'s timeout was lifted early.",
            )
            self.set_author(embed, after)
            embed.add_field(name="Member", value=format_user(after), inline=True)
            embed.add_field(name="Was Expiring", value=format_timestamp(before_until), inline=True)
            self.add_actor(embed, entry, name="Removed By")
            embed.set_footer(text=f"Member ID: {after.id}")

            await self.send_log(after.guild, embed)

    async def _log_nickname_change(self, before: nextcord.Member, after: nextcord.Member) -> None:
        before_nick = getattr(before, "nick", None)
        after_nick = getattr(after, "nick", None)

        if before_nick == after_nick:
            return

        entry = await self.audit(
            after.guild,
            nextcord.AuditLogAction.member_update,
            target_id=after.id,
            check=lambda candidate: audit_touched(candidate, "nick"),
        )

        embed = self.build_embed(
            "Nickname Changed",
            color_name="blue",
            fallback=0x3498DB,
            description=f"{after.mention} changed their nickname.",
        )
        self.set_author(embed, after)
        embed.add_field(name="Member", value=format_user(after), inline=False)
        embed.add_field(name="Before", value=clip(before_nick) if before_nick else "*None*", inline=True)
        embed.add_field(name="After", value=clip(after_nick) if after_nick else "*None*", inline=True)

        actor = getattr(entry, "user", None) if entry is not None else None

        if actor is not None and getattr(actor, "id", None) != after.id:
            self.add_actor(embed, entry, name="Changed By")

        embed.set_footer(text=f"Member ID: {after.id}")

        await self.send_log(after.guild, embed)


def setup(bot: APBot) -> None:
    bot.add_cog(MemberLog(bot))
