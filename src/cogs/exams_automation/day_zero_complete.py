import asyncio
from datetime import datetime
from typing import Optional

import nextcord
from nextcord import Interaction, slash_command
from nextcord.ext import commands, tasks

from config_handler import Config
from cogs.exams_automation.models import (
    EXAM_TZ,
    ExamAutomationManager,
    build_protocol_state,
    member_is_manual_controller,
)

config_path = "config.json"
conf = Config(config_path)
GUILD_ID = int(conf.get("guild_id"))


class ExamAutomation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.manager = ExamAutomationManager(bot)
        self._last_signature: Optional[tuple] = None
        self._test_task: Optional[asyncio.Task] = None
        self._test_active: bool = False
        self._manual_override_active: bool = False

        # Auto-start the protocol loop.
        #
        # Important:
        # The before_loop method arms the current signature first,
        # so the bot does NOT apply channel changes immediately on startup.
        if not self.protocol_sync_loop.is_running():
            self.protocol_sync_loop.start()

    def cog_unload(self) -> None:
        if self.protocol_sync_loop.is_running():
            self.protocol_sync_loop.cancel()

        if self._test_task and not self._test_task.done():
            self._test_task.cancel()

    async def _safe_defer(self, inter: Interaction) -> None:
        """
        Immediately acknowledges a slash command so Discord does not timeout.

        After this, use inter.followup.send(...), not inter.response.send_message(...).
        """
        if not inter.response.is_done():
            await inter.response.defer(ephemeral=True)

    async def _send_ephemeral(self, inter: Interaction, message: str) -> None:
        if inter.response.is_done():
            await inter.followup.send(message, ephemeral=True)
        else:
            await inter.response.send_message(message, ephemeral=True)

    async def _require_manual_role_after_defer(self, inter: Interaction) -> bool:
        """
        Permission check for slash commands that already used defer().
        """
        if not isinstance(inter.user, nextcord.Member):
            await inter.followup.send(
                "This command can only be used in the server.",
                ephemeral=True,
            )
            return False

        if not member_is_manual_controller(inter.user):
            await inter.followup.send(
                "You must have the **Chat Moderator** or **Admin** role to use this command.",
                ephemeral=True,
            )
            return False

        return True

    async def _require_manual_role(self, inter: Interaction) -> bool:
        """
        Kept for safety, but most commands below use the defer version.
        """
        if not isinstance(inter.user, nextcord.Member):
            await self._send_ephemeral(inter, "This command can only be used in the server.")
            return False

        if not member_is_manual_controller(inter.user):
            await self._send_ephemeral(
                inter,
                "You must have the **Chat Moderator** or **Admin** role to use this command.",
            )
            return False

        return True

    async def _sync_protocol_now(self, *, force: bool = False) -> str:
        guild = self.manager.get_guild()
        if guild is None:
            return "Guild not found."
        if self._manual_override_active and not force:
            return "Skipped protocol sync because manual override mode is active."
        if self._test_active and not force:
            return "Skipped protocol sync because a Day Zero / Day One test is currently active."

        state = build_protocol_state()
        signature = state.signature()

        if not force and signature == self._last_signature:
            return "No protocol change needed."

        report = await self.manager.apply_protocol(
            guild,
            state,
            reason=f"Exam protocol sync @ {state.now.isoformat()}",
        )

        self._last_signature = signature
        return report.to_text("Exam protocol sync")

    async def _run_day_zero_test_background(
        self,
        *,
        inter: Optional[Interaction],
        duration_seconds: int,
        started_by: str,
    ) -> None:
        """
        Background Day Zero test.

        This prevents slash-command timeout because the command responds first,
        then this function does the slow channel edits.
        """
        try:
            guild = self.manager.get_guild()
            if guild is None:
                if inter:
                    await inter.followup.send("Guild not found.", ephemeral=True)
                return

            self._test_active = True
            self._last_signature = None

            report = await self.manager.apply_day_zero(
                guild,
                reason=f"Manual Day Zero test by {started_by}",
            )

            if inter:
                await inter.followup.send(
                    report.to_text(
                        f"Day Zero test applied. Auto-undo in {duration_seconds // 60} minute(s)."
                    ),
                    ephemeral=True,
                )

            await asyncio.sleep(duration_seconds)

            report = await self.manager.open_everything(
                guild,
                reason="Automatic Day Zero test undo",
            )
            print(report.to_text("Automatic Day Zero test undo"))

            if inter:
                await inter.followup.send(
                    report.to_text("Day Zero test automatically undone"),
                    ephemeral=True,
                )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(f"[ExamAutomation] Day Zero background test failed: {exc}")
            if inter:
                try:
                    await inter.followup.send(
                        f"Day Zero test failed: {exc}",
                        ephemeral=True,
                    )
                except Exception:
                    pass

        finally:
            self._test_active = False
            self._test_task = None
            self._last_signature = None

    async def _run_day_zero_then_day_one_test_background(
        self,
        *,
        inter: Optional[Interaction],
        day_zero_seconds: int,
        day_one_seconds: int,
        started_by: str,
    ) -> None:
        """
        Background version of:

        Day Zero
        wait
        simulated Day One lockdown
        wait
        reopen everything
        """
        try:
            guild = self.manager.get_guild()
            if guild is None:
                if inter:
                    await inter.followup.send("Guild not found.", ephemeral=True)
                return

            self._test_active = True
            self._last_signature = None

            # Step 1: Apply Day Zero immediately.
            day_zero_report = await self.manager.apply_day_zero(
                guild,
                reason=f"Manual Day Zero + Day One test by {started_by}",
            )

            if inter:
                await inter.followup.send(
                    day_zero_report.to_text(
                        f"Day Zero test applied. "
                        f"Switching to Day One lockdown in {day_zero_seconds // 60} minute(s)."
                    ),
                    ephemeral=True,
                )

            # Step 2: Wait during Day Zero.
            await asyncio.sleep(day_zero_seconds)

            # Step 3: Simulate Day One exam lockdown.
            # Fake time: May 4, 2026 at 8:00 AM Eastern.
            # That is inside the testing window.
            day_one_test_time = datetime(2026, 5, 4, 8, 0, 0, tzinfo=EXAM_TZ)
            day_one_state = build_protocol_state(day_one_test_time)

            day_one_report = await self.manager.apply_protocol(
                guild,
                day_one_state,
                reason="Manual Day Zero + Day One test: simulated Day One lockdown",
            )

            print(day_one_report.to_text("Day One lockdown test started"))

            if inter:
                await inter.followup.send(
                    day_one_report.to_text(
                        f"Day One lockdown test applied. "
                        f"Auto-undo in {day_one_seconds // 60} minute(s)."
                    ),
                    ephemeral=True,
                )

            # Step 4: Wait during Day One lockdown.
            await asyncio.sleep(day_one_seconds)

            # Step 5: Undo by reopening everything.
            undo_report = await self.manager.open_everything(
                guild,
                reason="Automatic Day Zero + Day One test undo",
            )

            print(undo_report.to_text("Automatic Day Zero + Day One test undo"))

            if inter:
                await inter.followup.send(
                    undo_report.to_text("Day Zero + Day One test automatically undone"),
                    ephemeral=True,
                )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(f"[ExamAutomation] Day Zero + Day One background test failed: {exc}")
            if inter:
                try:
                    await inter.followup.send(
                        f"Day Zero + Day One test failed: {exc}",
                        ephemeral=True,
                    )
                except Exception:
                    pass

        finally:
            self._test_active = False
            self._test_task = None
            self._last_signature = None

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # Do not force-sync here.
        # The loop auto-starts, but before_loop arms the current signature first.
        print("[ExamAutomation] Ready. Auto-sync loop is enabled without startup force-sync.")

    @tasks.loop(minutes=1)
    async def protocol_sync_loop(self) -> None:
        """
        Runs every minute.

        It only applies changes when the protocol state signature changes.
        Since before_loop stores the current signature first, startup itself
        should not cause channel changes/spam.
        """
        try:
            summary = await self._sync_protocol_now(force=False)
            if summary != "No protocol change needed.":
                print(summary)
        except Exception as exc:
            print(f"[ExamAutomation] protocol sync loop failed: {exc}")

    @protocol_sync_loop.before_loop
    async def before_protocol_sync_loop(self) -> None:
        await self.bot.wait_until_ready()

        # Arm the automation without applying changes immediately.
        #
        # This prevents startup spam / startup reopening.
        # The bot will only apply changes when the protocol state changes
        # after this point.
        try:
            state = build_protocol_state()
            self._last_signature = state.signature()
            print(
                f"[ExamAutomation] Auto-sync armed at {state.now.isoformat()}. "
                "No startup channel changes were applied."
            )
        except Exception as exc:
            print(f"[ExamAutomation] Failed to arm startup signature: {exc}")

    @slash_command(
        name="close_all_channels",
        description="Emergency backup: close all essential and non-essential channels.",
        guild_ids=[GUILD_ID],
    )
    async def close_all_channels(self, inter: Interaction):
        await self._safe_defer(inter)

        if not await self._require_manual_role_after_defer(inter):
            return

        await inter.followup.send(
            "Closing all channels using the emergency backup flow...",
            ephemeral=True,
        )

        guild = self.manager.get_guild()
        if guild is None:
            await inter.followup.send("Guild not found.", ephemeral=True)
            return

        try:
            report = await self.manager.close_everything(
                guild,
                reason=f"Manual close_all_channels by {inter.user}",
            )
            self._manual_override_active = True
            self._last_signature = None
            await inter.followup.send(
                report.to_text("Emergency close all channels"),
                ephemeral=True,
            )
        except Exception as exc:
            await inter.followup.send(
                f"Emergency close failed: {exc}",
                ephemeral=True,
            )

    @slash_command(
        name="open_all_channels",
        description="Emergency backup: reopen channels according to the current protocol.",
        guild_ids=[GUILD_ID],
    )
    async def open_all_channels(self, inter: Interaction):
        await self._safe_defer(inter)

        if not await self._require_manual_role_after_defer(inter):
            return

        await inter.followup.send(
            "Reopening channels according to the current protocol state...",
            ephemeral=True,
        )

        guild = self.manager.get_guild()
        if guild is None:
            await inter.followup.send("Guild not found.", ephemeral=True)
            return

        try:
            self._manual_override_active = False
            state = build_protocol_state()
            report = await self.manager.apply_protocol(
                guild,
                state,
                reason=f"Manual open_all_channels by {inter.user}",
            )
            self._last_signature = state.signature()
            await inter.followup.send(
                report.to_text("Protocol-aware reopen"),
                ephemeral=True,
            )
        except Exception as exc:
            await inter.followup.send(
                f"Protocol-aware reopen failed: {exc}",
                ephemeral=True,
            )

    @slash_command(
        name="sync_exam_protocol",
        description="Force a full exam protocol sync right now.",
        guild_ids=[GUILD_ID],
    )
    async def sync_exam_protocol(self, inter: Interaction):
        await self._safe_defer(inter)

        if not await self._require_manual_role_after_defer(inter):
            return

        await inter.followup.send(
            "Forcing an exam protocol sync...",
            ephemeral=True,
        )

        try:
            self._manual_override_active = False
            summary = await self._sync_protocol_now(force=True)
            await inter.followup.send(summary, ephemeral=True)
        except Exception as exc:
            await inter.followup.send(
                f"Forced protocol sync failed: {exc}",
                ephemeral=True,
            )

    @slash_command(
        name="start_exam_auto_sync",
        description="Start automatic exam protocol syncing every minute.",
        guild_ids=[GUILD_ID],
    )
    async def start_exam_auto_sync(self, inter: Interaction):
        await self._safe_defer(inter)

        if not await self._require_manual_role_after_defer(inter):
            return

        if self.protocol_sync_loop.is_running():
            await inter.followup.send(
                "Automatic exam protocol syncing is already running.",
                ephemeral=True,
            )
            return

        try:
            state = build_protocol_state()
            self._last_signature = state.signature()
        except Exception:
            self._last_signature = None

        self.protocol_sync_loop.start()

        await inter.followup.send(
            "Automatic exam protocol syncing has been started. "
            "The bot will check the protocol every minute without force-syncing immediately.",
            ephemeral=True,
        )

    @slash_command(
        name="stop_exam_auto_sync",
        description="Stop automatic exam protocol syncing.",
        guild_ids=[GUILD_ID],
    )
    async def stop_exam_auto_sync(self, inter: Interaction):
        await self._safe_defer(inter)

        if not await self._require_manual_role_after_defer(inter):
            return

        if not self.protocol_sync_loop.is_running():
            await inter.followup.send(
                "Automatic exam protocol syncing is already stopped.",
                ephemeral=True,
            )
            return

        self.protocol_sync_loop.cancel()

        await inter.followup.send(
            "Automatic exam protocol syncing has been stopped.",
            ephemeral=True,
        )

    @slash_command(
        name="test_day_zero_cycle",
        description="Run a Day Zero test, then auto-undo it after a few minutes.",
        guild_ids=[GUILD_ID],
    )
    async def test_day_zero_cycle(
        self,
        inter: Interaction,
        duration_minutes: int = 10,
    ):
        await self._safe_defer(inter)

        if not await self._require_manual_role_after_defer(inter):
            return

        if duration_minutes < 1:
            duration_minutes = 1
        if duration_minutes > 10:
            duration_minutes = 10

        guild = self.manager.get_guild()
        if guild is None:
            await inter.followup.send("Guild not found.", ephemeral=True)
            return

        # Cancel any existing active test.
        if self._test_task and not self._test_task.done():
            self._test_task.cancel()

        await inter.followup.send(
            f"Starting Day Zero test in the background. "
            f"Duration: {duration_minutes} minute(s).",
            ephemeral=True,
        )

        self._test_task = asyncio.create_task(
            self._run_day_zero_test_background(
                inter=inter,
                duration_seconds=duration_minutes * 60,
                started_by=str(inter.user),
            )
        )

    @slash_command(
        name="test_day_zero_day_one_cycle",
        description="Run Day Zero, then simulated Day One lockdown, then auto-undo.",
        guild_ids=[GUILD_ID],
    )
    async def test_day_zero_day_one_cycle(
        self,
        inter: Interaction,
        day_zero_minutes: int = 3,
        day_one_minutes: int = 3,
    ):
        await self._safe_defer(inter)

        if not await self._require_manual_role_after_defer(inter):
            return

        if day_zero_minutes < 1:
            day_zero_minutes = 1
        if day_zero_minutes > 10:
            day_zero_minutes = 10

        if day_one_minutes < 1:
            day_one_minutes = 1
        if day_one_minutes > 10:
            day_one_minutes = 10

        guild = self.manager.get_guild()
        if guild is None:
            await inter.followup.send("Guild not found.", ephemeral=True)
            return

        # Cancel any existing active test.
        if self._test_task and not self._test_task.done():
            self._test_task.cancel()

        await inter.followup.send(
            f"Starting Day Zero + Day One test in the background.\n"
            f"Day Zero: {day_zero_minutes} minute(s)\n"
            f"Day One lockdown: {day_one_minutes} minute(s)\n"
            f"I'll send updates as each phase finishes applying.",
            ephemeral=True,
        )

        self._test_task = asyncio.create_task(
            self._run_day_zero_then_day_one_test_background(
                inter=inter,
                day_zero_seconds=day_zero_minutes * 60,
                day_one_seconds=day_one_minutes * 60,
                started_by=str(inter.user),
            )
        )

    @slash_command(
        name="undo_day_zero_test",
        description="Immediately undo the active Day Zero / Day One test and reopen everything.",
        guild_ids=[GUILD_ID],
    )
    async def undo_day_zero_test(self, inter: Interaction):
        await self._safe_defer(inter)

        if not await self._require_manual_role_after_defer(inter):
            return

        guild = self.manager.get_guild()
        if guild is None:
            await inter.followup.send("Guild not found.", ephemeral=True)
            return

        if self._test_task and not self._test_task.done():
            self._test_task.cancel()

        await inter.followup.send(
            "Undoing the active Day Zero / Day One test and reopening everything...",
            ephemeral=True,
        )

        try:
            report = await self.manager.open_everything(
                guild,
                reason=f"Manual Day Zero / Day One undo by {inter.user}",
            )

            self._test_active = False
            self._test_task = None
            self._last_signature = None

            await inter.followup.send(
                report.to_text("Day Zero / Day One test undone"),
                ephemeral=True,
            )

        except Exception as exc:
            await inter.followup.send(
                f"Undo Day Zero / Day One test failed: {exc}",
                ephemeral=True,
            )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(ExamAutomation(bot))