from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from zoneinfo import ZoneInfo

import nextcord

# =========================
# Time / role configuration
# =========================

EXAM_TZ = ZoneInfo("America/New_York")
MANUAL_ALLOWED_ROLE_NAMES = {"Chat Moderator", "Admin"}

# Staff-ish roles that should NOT be closed out of channels.
STAFF_ROLE_KEYWORDS = (
    "Admin",
    "Moderator",
    "Educator",
    "Teacher"
)

# =========================
# Channel / category config
# =========================

ALWAYS_OPEN_CHANNELS = {
    "help-i-cant-see-channels",
    "lounge-signup",
    "ap-exam-announcements-2026",
}

ESSENTIAL_GENERAL_CHANNELS = [
    "general-1",
    "school-advice",
    "emotional-support",
    "non-ap-help",
    "welcome",
    "server-feedback-2026",
    "bot-feedback",
    "contest-submission1",
    "contest-submission2",
    "contest-submission3",
]

# Updated from the 2026 protocol.
NONESSENTIAL_TEXT_CHANNEL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "general-2": ("general-2",),
    "college": ("college",),
    "bot-commands": ("bot-commands",),
    "post-ap-math": ("post-ap-math",),
    "higher-bio": ("higher-bio",),
    "higher-chem": ("higher-chem",),
    "higher-cs": ("higher-cs",),
    "higher-physics": ("higher-physics",),
    "aphome-econ": ("aphome-econ",),
    "apresearch": ("apresearch",),
    "apart-design": ("apart-design",),
}

STUDY_TEXT_CHANNEL_IDS = [
    1498714556275490941,  # study-room-1
    1498714556275490942,  # study-room-2
]

# Old IDs preserved from your older automation.
STUDY_SESSION_VC_IDS = [
    1498714556275490943,
    1498714556275490944,
    1498714556275490945,
    1498714556275490946,
]

DEFAULT_STUDY_SESSION_NAMES = [
    "Study Session 1",
    "Study Session 2",
    "Study Session 3",
    "Study Session 4",
]

CATEGORY_ALIASES: Dict[str, Tuple[str, ...]] = {
    "lounge": ("Lounge",),
    "events": ("Events",),
    "voice": ("Voice Channels",),
    "lecture": ("Lecture Stages",),
    "subjects": ("Subject Channels",),
    "season_misc": ("AP Exams 2026",),
}




SUBJECT_CHANNEL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "apbio": ("apbio",),
    "aplatin": ("aplatin",),
    "apeuro": ("apeuro",),
    "apmicro": ("apmicro",),
    "apchem": ("apchem",),
    "aphug": ("aphug",),
    "apgov-us": ("apgov-us",),
    "aplit": ("aplit",),
    "apgov-comp": ("apgov-comp",),
    "apphysics1": ("apphysics1",),
    "apphysics2": ("apphysics2",),
    "apwh-modern": ("apwh-modern",),
    "apafam-studies": ("apafam-studies",),
    "apstats": ("apstats",),
    "apitalian": ("apitalian",),
    "apush": ("apush",),
    "apchinese": ("apchinese",),
    "apmacro": ("apmacro",),
    "apcalc-ab": ("apcalc-ab",),
    "apcalc-bc": ("apcalc-bc",),
    "apmusictheory": ("apmusictheory",),
    "apseminar": ("apseminar",),
    "apfrench": ("apfrench",),
    "apprecalc": ("apprecalc",),
    "apjapanese": ("apjapanese",),
    "appsych": ("appsych",),
    "aplang": ("aplang",),
    "apgerman": ("apgerman",),
    "apphysicsc-mech": ("apphysicsc-mech",),
    "apspanish-lit": ("apspanish-lit",),
    "aparthistory": ("aparthistory",),
    "apspanish-lang": ("apspanish-lang",),
    "apcsp": ("apcsp",),
    "apphysicsc-em": ("apphysicsc-em",),
    "apes": ("apes",),
    "apcsa": ("apcsa",),
}

SUBJECT_LABELS: Dict[str, str] = {
    "apbio": "AP Biology",
    "aplatin": "AP Latin",
    "apeuro": "AP European History",
    "apmicro": "AP Microeconomics",
    "apchem": "AP Chemistry",
    "aphug": "AP Human Geography",
    "apgov-us": "AP U.S. Government",
    "aplit": "AP English Literature",
    "apgov-comp": "AP Comparative Government",
    "apphysics1": "AP Physics 1",
    "apphysics2": "AP Physics 2",
    "apwh-modern": "AP World History",
    "apafam-studies": "AP African American Studies",
    "apstats": "AP Statistics",
    "apitalian": "AP Italian",
    "apush": "AP U.S. History",
    "apchinese": "AP Chinese",
    "apmacro": "AP Macroeconomics",
    "apcalc-ab": "AP Calculus AB",
    "apcalc-bc": "AP Calculus BC",
    "apmusictheory": "AP Music Theory",
    "apseminar": "AP Seminar",
    "apfrench": "AP French",
    "apprecalc": "AP Precalculus",
    "apjapanese": "AP Japanese",
    "appsych": "AP Psychology",
    "aplang": "AP English Language",
    "apgerman": "AP German",
    "apphysicsc-mech": "AP Physics C: Mechanics",
    "apspanish-lit": "AP Spanish Literature",
    "aparthistory": "AP Art History",
    "apspanish-lang": "AP Spanish Language",
    "apcsp": "AP Computer Science Principles",
    "apphysicsc-em": "AP Physics C: E&M",
    "apes": "AP Environmental Science",
    "apcsa": "AP Computer Science A",
}

# Use the protocol dates/times from the 2026 document.
# Night-before study sessions start at 7 PM EDT.
# Essential channels close 8 AM -> 7 PM on exam days.
# Once tested, subject channels stay closed until FRQ release / season end.
EXAM_SCHEDULE: Dict[date, List[str]] = {
    date(2026, 5, 4): ["apbio", "aplatin", "apeuro", "apmicro"],
    date(2026, 5, 5): ["apchem", "aphug", "apgov-us"],
    date(2026, 5, 6): ["aplit", "apgov-comp", "apphysics1"],
    date(2026, 5, 7): ["apphysics2", "apwh-modern", "apafam-studies", "apstats"],
    date(2026, 5, 8): ["apitalian", "apush", "apchinese", "apmacro"],
    date(2026, 5, 11): ["apcalc-ab", "apcalc-bc", "apmusictheory", "apseminar"],
    date(2026, 5, 12): ["apfrench", "apprecalc", "apjapanese", "appsych"],
    date(2026, 5, 13): ["aplang", "apgerman", "apphysicsc-mech", "apspanish-lit"],
    date(2026, 5, 14): ["aparthistory", "apspanish-lang", "apcsp", "apphysicsc-em"],
    date(2026, 5, 15): ["apes", "apcsa"],
}

SEASON_START = datetime(2026, 5, 4, 8, 0, 0, tzinfo=EXAM_TZ)
SEASON_END = datetime(2026, 5, 15, 19, 0, 0, tzinfo=EXAM_TZ)
DAY_ZERO_START = datetime(2026, 5, 3, 19, 0, 0, tzinfo=EXAM_TZ)

# If FRQs are NOT released for some subjects at the end of the season,
# add their canonical channel names here and they will remain closed.
POST_SEASON_FRQ_HOLDS: Set[str] = set()

# =========================
# Data models
# =========================

@dataclass
class ActionReport:
    changed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    untouched: List[str] = field(default_factory=list)

    def add_changed(self, message: str) -> None:
        self.changed.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_missing(self, message: str) -> None:
        self.missing.append(message)

    def add_untouched(self, message: str) -> None:
        self.untouched.append(message)

    def to_text(self, title: str = "Automation report") -> str:
        parts = [f"**{title}**"]

        if self.changed:
            parts.append(f"**Changed ({len(self.changed)}):**")
            parts.extend(f"- {item}" for item in self.changed[:30])

        if self.warnings:
            parts.append(f"**Warnings ({len(self.warnings)}):**")
            parts.extend(f"- {item}" for item in self.warnings[:20])

        if self.missing:
            parts.append(f"**Missing ({len(self.missing)}):**")
            parts.extend(f"- {item}" for item in self.missing[:20])

        if not self.changed and not self.warnings and not self.missing:
            parts.append("- No changes were needed.")

        return "\n".join(parts)


@dataclass(frozen=True)
class ProtocolState:
    now: datetime
    testing_window: bool
    nonessential_closed: bool
    essential_open: bool
    open_subjects: frozenset[str]
    closed_subjects: frozenset[str]
    study_subjects: Tuple[str, ...]
    season_over: bool

    def signature(self) -> Tuple:
        return (
            self.now.date().isoformat(),
            self.testing_window,
            self.nonessential_closed,
            self.essential_open,
            tuple(sorted(self.open_subjects)),
            tuple(sorted(self.closed_subjects)),
            self.study_subjects,
            self.season_over,
        )


# =========================
# Utility helpers
# =========================

def exam_now() -> datetime:
    return datetime.now(EXAM_TZ)


def normalize(name: str) -> str:
    return name.strip().lower()


def role_name_set(member: nextcord.Member) -> Set[str]:
    return {role.name for role in member.roles}


def member_is_manual_controller(member: nextcord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    return any(role.name in MANUAL_ALLOWED_ROLE_NAMES for role in member.roles)


def all_canonical_subjects() -> Set[str]:
    return set(SUBJECT_CHANNEL_ALIASES.keys())


def canonical_for_subject_channel_name(name: str) -> Optional[str]:
    lowered = normalize(name)
    for canonical, aliases in SUBJECT_CHANNEL_ALIASES.items():
        if lowered in {normalize(alias) for alias in aliases}:
            return canonical
    return None


def is_staff_role(role: nextcord.Role) -> bool:
    lowered = role.name.lower()
    return any(keyword in lowered for keyword in STAFF_ROLE_KEYWORDS)


def is_ap_like_role(role: nextcord.Role) -> bool:
    lowered = role.name.lower()
    if is_staff_role(role):
        return False
    if lowered.startswith("ap "):
        return True
    if role.name in {"Post-AP Math", "Higher CS", "Higher Other", "Higher Bio", "Higher Chem", "Higher Physics"}:
        return True
    return False


def get_category(guild: nextcord.Guild, names: Sequence[str]) -> Optional[nextcord.CategoryChannel]:
    lowered = {normalize(name) for name in names}
    for category in guild.categories:
        if normalize(category.name) in lowered:
            return category
    return None


def get_channel_by_aliases(
    guild: nextcord.Guild,
    aliases: Sequence[str],
) -> Optional[nextcord.abc.GuildChannel]:
    lowered_aliases = {normalize(alias) for alias in aliases}
    for channel in guild.channels:
        if normalize(channel.name) in lowered_aliases:
            return channel
    return None


def subject_channel_aliases(canonical_name: str) -> Tuple[str, ...]:
    return SUBJECT_CHANNEL_ALIASES.get(canonical_name, (canonical_name,))


def get_exam_dates() -> List[date]:
    return sorted(EXAM_SCHEDULE.keys())


def current_study_subjects(now: datetime) -> Tuple[str, ...]:
    exam_dates = get_exam_dates()

    for idx, exam_day in enumerate(exam_dates):
        if idx == 0:
            window_start_day = exam_day - timedelta(days=1)
        else:
            window_start_day = exam_dates[idx - 1]

        window_start = datetime.combine(
            window_start_day,
            time(19, 0),
            tzinfo=EXAM_TZ,
        )

        window_end = datetime.combine(
            exam_day,
            time(8, 0),
            tzinfo=EXAM_TZ,
        )

        if window_start <= now < window_end:
            return tuple(EXAM_SCHEDULE[exam_day])

    return tuple()


def tested_subjects_for_time(now: datetime) -> Set[str]:
    closed_subjects: Set[str] = set()

    for exam_day, subjects in EXAM_SCHEDULE.items():
        close_start = datetime.combine(
            exam_day,
            time(19, 0),
            tzinfo=EXAM_TZ,
        )

        reopen_time = close_start + timedelta(days=2)

        if close_start <= now < reopen_time:
            closed_subjects.update(subjects)

    return closed_subjects


def in_testing_window(now: datetime) -> bool:
    if now.date() not in EXAM_SCHEDULE:
        return False

    start = datetime.combine(now.date(), time(8, 0), tzinfo=EXAM_TZ)
    end = datetime.combine(now.date(), time(19, 0), tzinfo=EXAM_TZ)
    return start <= now < end


def build_protocol_state(now: Optional[datetime] = None) -> ProtocolState:
    now = now or exam_now()
    testing_window = in_testing_window(now)
    season_over = now >= SEASON_END
    season_started = now >= SEASON_START

    nonessential_closed = now >= DAY_ZERO_START and not season_over
    essential_open = not testing_window

    if not season_started:
        open_subjects = all_canonical_subjects()
        closed_subjects = set()
    elif season_over:
        tested = tested_subjects_for_time(now)
        closed_subjects = tested | set(POST_SEASON_FRQ_HOLDS)
        open_subjects = all_canonical_subjects() - closed_subjects
    elif testing_window:
        open_subjects = set()
        closed_subjects = all_canonical_subjects()
    else:
        tested = tested_subjects_for_time(now)
        open_subjects = all_canonical_subjects() - tested
        closed_subjects = tested

    return ProtocolState(
        now=now,
        testing_window=testing_window,
        nonessential_closed=nonessential_closed,
        essential_open=essential_open,
        open_subjects=frozenset(open_subjects),
        closed_subjects=frozenset(closed_subjects),
        study_subjects=current_study_subjects(now),
        season_over=season_over,
    )


# =========================
# Channel wrappers
# =========================

class APChannel:
    ROLE_GATED_CHANNEL_ROLES: Dict[str, Tuple[str, ...]] = {
        "post-ap-math": ("Post-AP Math",),
        "higher-bio": ("Higher Bio",),
        "higher-chem": ("Higher Chem",),
        "higher-cs": ("Higher CS",),
        "higher-physics": ("Higher Physics",),
    }

    def __init__(self, guild: nextcord.Guild, channel: nextcord.abc.GuildChannel):
        self.guild = guild
        self.channel = channel

    def is_subject_channel(self) -> bool:
        subject_category = get_category(self.guild, CATEGORY_ALIASES["subjects"])
        if subject_category and self.channel.category_id == subject_category.id:
            return True

        return canonical_for_subject_channel_name(self.channel.name) is not None

    def is_lounge_channel(self) -> bool:
        lounge_category = get_category(self.guild, CATEGORY_ALIASES["lounge"])
        if lounge_category and self.channel.category_id == lounge_category.id:
            return True

        return False

    def _role_by_name(self, role_name: str) -> Optional[nextcord.Role]:
        wanted = normalize(role_name)

        for role in self.guild.roles:
            if normalize(role.name) == wanted:
                return role

        return None

    def _explicit_role_gate_roles(self) -> List[nextcord.Role]:
        channel_name = normalize(self.channel.name)
        role_names = self.ROLE_GATED_CHANNEL_ROLES.get(channel_name, tuple())

        roles: List[nextcord.Role] = []

        for role_name in role_names:
            role = self._role_by_name(role_name)
            if role:
                roles.append(role)

        return roles

    def _overwrite_roles_matching(
        self,
        *,
        include_ap_like: bool = False,
        include_helper_lecture: bool = False,
        include_lounge: bool = False,
    ) -> List[nextcord.Role]:
        roles: List[nextcord.Role] = []

        for target in self.channel.overwrites:
            if not isinstance(target, nextcord.Role):
                continue

            if is_staff_role(target):
                continue

            should_include = False
            lowered = target.name.lower()

            if include_ap_like and is_ap_like_role(target):
                should_include = True

            if include_helper_lecture and (
                "helper" in lowered or "lecture" in lowered
            ):
                should_include = True

            if include_lounge and "lounge:" in lowered:
                should_include = True

            if should_include and target not in roles:
                roles.append(target)

        return roles

    def _subject_roles_to_toggle(self) -> List[nextcord.Role]:
        return self._overwrite_roles_matching(
            include_ap_like=True,
            include_helper_lecture=True,
        )

    def _lounge_roles_to_toggle(self) -> List[nextcord.Role]:
        return self._overwrite_roles_matching(
            include_lounge=True,
        )

    def roles_to_toggle(self) -> List[nextcord.Role]:
        if self.channel.name in ALWAYS_OPEN_CHANNELS:
            return []

        # Lounge category should use Lounge: roles, not @everyone.
        if self.is_lounge_channel():
            return self._lounge_roles_to_toggle()

        # Explicit role-gated channels.
        explicit_roles = self._explicit_role_gate_roles()
        if explicit_roles:
            return explicit_roles

        # Subject channels should use AP/helper/lecture roles.
        if self.is_subject_channel():
            subject_roles = self._subject_roles_to_toggle()
            if subject_roles:
                return subject_roles

            # Safety: never fall back to @everyone for subject channels.
            return []

        # Other AP/Higher style channels with role overwrites.
        overwrite_roles = self._overwrite_roles_matching(
            include_ap_like=True,
            include_helper_lecture=False,
            include_lounge=False,
        )
        if overwrite_roles:
            return overwrite_roles

        # Normal public channels use @everyone.
        return [self.guild.default_role]

    def is_role_gated_channel(self) -> bool:
        if self.is_lounge_channel():
            return True

        if self._explicit_role_gate_roles():
            return True

        if self.is_subject_channel():
            return True

        channel_name = normalize(self.channel.name)
        if channel_name in self.ROLE_GATED_CHANNEL_ROLES:
            return True

        return False

    def _can_send_status_message(self) -> bool:
        return isinstance(self.channel, nextcord.TextChannel)

    def _is_voice_like_channel(self) -> bool:
        return isinstance(
            self.channel,
            (
                nextcord.VoiceChannel,
                nextcord.StageChannel,
            ),
        )

    def _role_can_effectively_access(self, role: nextcord.Role) -> bool:
        """
        This checks the actual effective permissions, including category inheritance.

        This prevents spam like saying "Reopening general-1" when it was already
        visible/open through inherited permissions.
        """
        try:
            perms = self.channel.permissions_for(role)

            if self._is_voice_like_channel():
                return bool(perms.view_channel and perms.connect)

            return bool(perms.view_channel)

        except Exception:
            return False

    def _role_can_effectively_send_or_speak(self, role: nextcord.Role) -> bool:
        try:
            perms = self.channel.permissions_for(role)

            if self._is_voice_like_channel():
                return bool(perms.connect or perms.speak)

            return bool(perms.send_messages)

        except Exception:
            return False

    def _overwrite_is_closed_for_role(self, role: nextcord.Role) -> bool:
        """
        Explicit overwrite check.

        A channel is considered closed for automation purposes if the target role
        has explicit denies. If a full deny fails, backup denies still count.
        """
        overwrite = self.channel.overwrites_for(role)

        if self._is_voice_like_channel():
            return (
                overwrite.view_channel is False
                or overwrite.connect is False
                or overwrite.speak is False
            )

        return (
            overwrite.view_channel is False
            or overwrite.read_messages is False
            or overwrite.send_messages is False
            or overwrite.read_message_history is False
        )

    def _overwrite_is_open_for_role(self, role: nextcord.Role) -> bool:
        """
        For message spam prevention, don't require explicit True.
        If the role can effectively access the channel, treat it as already open.
        """
        return self._role_can_effectively_access(role)

    def _everyone_is_blocked(self) -> bool:
        overwrite = self.channel.overwrites_for(self.guild.default_role)

        if self._is_voice_like_channel():
            return (
                overwrite.view_channel is False
                or overwrite.connect is False
                or overwrite.speak is False
            )

        return (
            overwrite.view_channel is False
            or overwrite.read_messages is False
            or overwrite.send_messages is False
            or overwrite.read_message_history is False
        )

    async def _send_status_embed(
        self,
        report: ActionReport,
        *,
        opened: bool,
    ) -> None:
        """
        Sends old-version-style channel messages only when a real state change happened.
        """
        if not self._can_send_status_message():
            return

        try:
            if opened:
                embed = nextcord.Embed(color=0x00FF00)
                embed.add_field(
                    name="",
                    value=f"Reopening {self.channel.mention}.",
                    inline=False,
                )
            else:
                embed = nextcord.Embed(color=0xFF0000)
                embed.add_field(
                    name="",
                    value=f"Shutting down {self.channel.mention}.",
                    inline=False,
                )

            embed.timestamp = datetime.now(EXAM_TZ)
            await self.channel.send(embed=embed)

        except Exception as exc:
            report.add_warning(
                f"Could not send status message in `{self.channel.name}`: {exc}"
            )

    async def _set_permissions_primary_close(
        self,
        target: nextcord.Role,
        *,
        reason: str,
    ) -> None:
        """
        Main close attempt.
        """
        await self.channel.set_permissions(
            target,
            view_channel=False,
            read_messages=False,
            send_messages=False,
            connect=False,
            speak=False,
            reason=reason,
        )

    async def _set_permissions_backup_close(
        self,
        target: nextcord.Role,
        *,
        reason: str,
    ) -> None:
        """
        Backup close attempt.

        Used if Discord refuses a full view/read close, like for some special
        onboarding/community-related channels.

        This tries to at least stop sending/speaking/connecting and hide history.
        """
        await self.channel.set_permissions(
            target,
            send_messages=False,
            connect=False,
            speak=False,
            read_message_history=False,
            reason=reason,
        )

    async def _set_permissions_primary_open(
        self,
        target: nextcord.Role,
        *,
        reason: str,
    ) -> None:
        """
        Main reopen attempt.
        """
        await self.channel.set_permissions(
            target,
            view_channel=True,
            read_messages=True,
            send_messages=True,
            connect=True,
            speak=True,
            read_message_history=True,
            reason=reason,
        )

    async def _set_permissions_backup_open(
        self,
        target: nextcord.Role,
        *,
        reason: str,
    ) -> None:
        """
        Backup reopen attempt.

        This undoes backup lockdown permissions.
        """
        await self.channel.set_permissions(
            target,
            send_messages=True,
            connect=True,
            speak=True,
            read_message_history=True,
            reason=reason,
        )

    async def _deny_everyone_for_role_gated_channel(
        self,
        report: ActionReport,
        reason: str,
    ) -> bool:
        """
        Safety cleanup.

        Returns True only if @everyone actually had to be changed.
        """
        if not self.is_role_gated_channel():
            return False

        if self._everyone_is_blocked():
            return False

        try:
            try:
                await self._set_permissions_primary_close(
                    self.guild.default_role,
                    reason=reason,
                )
            except Exception:
                await self._set_permissions_backup_close(
                    self.guild.default_role,
                    reason=reason,
                )

            report.add_changed(
                f"Protected `{self.channel.name}` from `@everyone` access."
            )
            return True

        except Exception as exc:
            report.add_warning(
                f"Failed protecting `{self.channel.name}` from `@everyone`: {exc}"
            )
            return False

    async def close(self, report: ActionReport, reason: str) -> None:
        roles = self.roles_to_toggle()

        if not roles:
            report.add_untouched(
                f"No matching roles found to close for `{self.channel.name}`."
            )
            return

        roles_needing_close = []

        for role in roles:
            if self._role_can_effectively_access(role) or self._role_can_effectively_send_or_speak(role):
                roles_needing_close.append(role)

        # Safety cleanup can happen silently, but it should not cause a
        # "Shutting down" message by itself.
        await self._deny_everyone_for_role_gated_channel(report, reason)

        if not roles_needing_close:
            report.add_untouched(f"`{self.channel.name}` was already closed.")
            return

        # Send shutdown message only when a real close is happening.
        await self._send_status_embed(report, opened=False)

        for role in roles_needing_close:
            try:
                try:
                    await self._set_permissions_primary_close(
                        role,
                        reason=reason,
                    )
                except Exception:
                    # Backup: if full close fails, at least block sending,
                    # connecting/speaking, and message history.
                    await self._set_permissions_backup_close(
                        role,
                        reason=reason,
                    )

                report.add_changed(f"Closed `{self.channel.name}` for `{role.name}`.")

            except Exception as exc:
                # Never crash the automation.
                report.add_warning(
                    f"Failed closing `{self.channel.name}` for `{role.name}`: {exc}"
                )

    async def open(self, report: ActionReport, reason: str) -> None:
        roles = self.roles_to_toggle()

        if not roles:
            report.add_untouched(
                f"No matching roles found to open for `{self.channel.name}`."
            )
            return

        roles_needing_open = [
            role for role in roles
            if not self._role_can_effectively_access(role)
        ]

        # Keep @everyone blocked on role-gated channels, but don't count that
        # as a reason to announce "Reopening".
        await self._deny_everyone_for_role_gated_channel(report, reason)

        if not roles_needing_open:
            report.add_untouched(f"`{self.channel.name}` was already open.")
            return

        for role in roles_needing_open:
            try:
                try:
                    await self._set_permissions_primary_open(
                        role,
                        reason=reason,
                    )
                except Exception:
                    await self._set_permissions_backup_open(
                        role,
                        reason=reason,
                    )

                report.add_changed(f"Opened `{self.channel.name}` for `{role.name}`.")

            except Exception as exc:
                # Never crash the automation.
                report.add_warning(
                    f"Failed opening `{self.channel.name}` for `{role.name}`: {exc}"
                )

        # Send reopen message only when something was actually reopened.
        await self._send_status_embed(report, opened=True)

class ExamAutomationManager:
    def __init__(self, bot: nextcord.ext.commands.Bot):
        self.bot = bot

    def get_guild(self) -> Optional[nextcord.Guild]:
        guild_id = getattr(self.bot, "guild_id", None)
        if guild_id:
            return self.bot.get_guild(guild_id)

        # Fallback for APBot-style config.
        if hasattr(self.bot, "config"):
            try:
                return self.bot.get_guild(int(self.bot.config.get("guild_id")))
            except Exception:
                return None

        return None

    def resolve_channel(
        self,
        guild: nextcord.Guild,
        aliases: Sequence[str],
    ) -> Optional[nextcord.abc.GuildChannel]:
        return get_channel_by_aliases(guild, aliases)

    def resolve_subject_channel(
        self,
        guild: nextcord.Guild,
        canonical_name: str,
    ) -> Optional[nextcord.abc.GuildChannel]:
        return self.resolve_channel(guild, subject_channel_aliases(canonical_name))

    def iter_category_channels(
        self,
        guild: nextcord.Guild,
        category_key: str,
        *,
        exclude_names: Optional[Set[str]] = None,
    ) -> Iterable[nextcord.abc.GuildChannel]:
        exclude_names = {normalize(name) for name in (exclude_names or set())}
        category = get_category(guild, CATEGORY_ALIASES[category_key])
        if not category:
            return []

        return [channel for channel in category.channels if normalize(channel.name) not in exclude_names]

    async def ensure_channel_state(
        self,
        guild: nextcord.Guild,
        aliases: Sequence[str],
        *,
        opened: bool,
        report: ActionReport,
        reason: str,
    ) -> None:
        channel = self.resolve_channel(guild, aliases)
        if not channel:
            report.add_missing(f"Channel not found for aliases: {', '.join(aliases)}")
            return

        wrapped = APChannel(guild, channel)
        if opened:
            await wrapped.open(report, reason)
        else:
            await wrapped.close(report, reason)

    async def ensure_subject_state(
        self,
        guild: nextcord.Guild,
        canonical_name: str,
        *,
        opened: bool,
        report: ActionReport,
        reason: str,
    ) -> None:
        channel = self.resolve_subject_channel(guild, canonical_name)
        if not channel:
            report.add_missing(f"Subject channel missing: {canonical_name}")
            return

        wrapped = APChannel(guild, channel)
        if opened:
            await wrapped.open(report, reason)
        else:
            await wrapped.close(report, reason)

    async def ensure_category_state(
        self,
        guild: nextcord.Guild,
        category_key: str,
        *,
        opened: bool,
        report: ActionReport,
        reason: str,
        exclude_names: Optional[Set[str]] = None,
    ) -> None:
        channels = list(self.iter_category_channels(guild, category_key, exclude_names=exclude_names))
        if not channels:
            report.add_missing(f"Category missing or empty: {category_key}")
            return

        for channel in channels:
            wrapped = APChannel(guild, channel)
            if opened:
                await wrapped.open(report, reason)
            else:
                await wrapped.close(report, reason)

    async def ensure_study_voice_channels(
        self,
        guild: nextcord.Guild,
        study_subjects: Sequence[str],
        *,
        opened: bool,
        report: ActionReport,
        reason: str,
    ) -> None:
        for idx, channel_id in enumerate(STUDY_SESSION_VC_IDS):
            channel = guild.get_channel(channel_id)
            if channel is None:
                report.add_missing(f"Study session VC missing for id `{channel_id}`.")
                continue

            try:
                if opened and idx < len(study_subjects):
                    subject = study_subjects[idx]
                    label = SUBJECT_LABELS.get(subject, subject)
                    await channel.edit(name=label, reason=reason)
                    await channel.set_permissions(
                        guild.default_role,
                        read_messages=True,
                        connect=True,
                        speak=True,
                        reason=reason,
                    )
                    report.add_changed(f"Opened study VC `{channel.name}` for `{label}`.")
                else:
                    fallback_name = DEFAULT_STUDY_SESSION_NAMES[idx]
                    await channel.edit(name=fallback_name, reason=reason)
                    await channel.set_permissions(
                        guild.default_role,
                        read_messages=False,
                        connect=False,
                        speak=False,
                        reason=reason,
                    )
                    report.add_changed(f"Closed study VC `{channel.name}`.")
            except Exception as exc:
                report.add_warning(f"Failed updating study VC `{channel_id}`: {exc}")

    async def ensure_study_text_channels(
        self,
        guild: nextcord.Guild,
        *,
        opened: bool,
        report: ActionReport,
        reason: str,
    ) -> None:
        for channel_id in STUDY_TEXT_CHANNEL_IDS:
            channel = guild.get_channel(channel_id)

            if channel is None:
                report.add_missing(f"Study text channel missing for id `{channel_id}`.")
                continue

            wrapped = APChannel(guild, channel)

            if opened:
                await wrapped.open(report, reason)
            else:
                await wrapped.close(report, reason)


    async def open_everything(self, guild: nextcord.Guild, reason: str) -> ActionReport:
        report = ActionReport()

        for aliases in NONESSENTIAL_TEXT_CHANNEL_ALIASES.values():
            await self.ensure_channel_state(guild, aliases, opened=True, report=report, reason=reason)


        for channel_name in ESSENTIAL_GENERAL_CHANNELS:
            await self.ensure_channel_state(guild, (channel_name,), opened=True, report=report, reason=reason)

        for subject in sorted(all_canonical_subjects()):
            await self.ensure_subject_state(guild, subject, opened=True, report=report, reason=reason)

        await self.ensure_category_state(
            guild,
            "lounge",
            opened=True,
            report=report,
            reason=reason,
            exclude_names={"lounge-signup"},
        )
        await self.ensure_category_state(guild, "events", opened=True, report=report, reason=reason)
        await self.ensure_category_state(guild, "voice", opened=True, report=report, reason=reason)
        await self.ensure_category_state(guild, "lecture", opened=True, report=report, reason=reason)
        await self.ensure_category_state(
            guild,
            "season_misc",
            opened=True,
            report=report,
            reason=reason,
            exclude_names=set(),
        )

        for always_open in ALWAYS_OPEN_CHANNELS:
            await self.ensure_channel_state(guild, (always_open,), opened=True, report=report, reason=reason)

        await self.ensure_study_text_channels(guild, opened=True, report=report, reason=reason)
        await self.ensure_study_voice_channels(
            guild,
            tuple(),
            opened=True,
            report=report,
            reason=reason,
        )

        return report

    async def apply_day_zero(self, guild: nextcord.Guild, reason: str) -> ActionReport:
        report = ActionReport()

        # Close non-essential until season end.
        for aliases in NONESSENTIAL_TEXT_CHANNEL_ALIASES.values():
            await self.ensure_channel_state(guild, aliases, opened=False, report=report, reason=reason)

        await self.ensure_category_state(
            guild,
            "lounge",
            opened=False,
            report=report,
            reason=reason,
            exclude_names={"lounge-signup"},
        )
        await self.ensure_category_state(guild, "events", opened=False, report=report, reason=reason)
        await self.ensure_category_state(guild, "voice", opened=False, report=report, reason=reason)

        # Keep essential channels open on Day Zero.
        for channel_name in ESSENTIAL_GENERAL_CHANNELS:
            await self.ensure_channel_state(guild, (channel_name,), opened=True, report=report, reason=reason)

        await self.ensure_category_state(guild, "lecture", opened=True, report=report, reason=reason)

        # Day Zero study setup is for first exam day.
        first_day_subjects = EXAM_SCHEDULE[min(get_exam_dates())]
        await self.ensure_study_text_channels(guild, opened=True, report=report, reason=reason)
        await self.ensure_study_voice_channels(
            guild,
            first_day_subjects,
            opened=True,
            report=report,
            reason=reason,
        )

        for always_open in ALWAYS_OPEN_CHANNELS:
            await self.ensure_channel_state(guild, (always_open,), opened=True, report=report, reason=reason)

        return report

    async def close_everything(self, guild: nextcord.Guild, reason: str) -> ActionReport:
        report = ActionReport()

        for aliases in NONESSENTIAL_TEXT_CHANNEL_ALIASES.values():
            await self.ensure_channel_state(guild, aliases, opened=False, report=report, reason=reason)

        for channel_name in ESSENTIAL_GENERAL_CHANNELS:
            await self.ensure_channel_state(guild, (channel_name,), opened=False, report=report, reason=reason)

        for subject in sorted(all_canonical_subjects()):
            await self.ensure_subject_state(guild, subject, opened=False, report=report, reason=reason)

        await self.ensure_category_state(
            guild,
            "lounge",
            opened=False,
            report=report,
            reason=reason,
            exclude_names={"lounge-signup"},
        )
        await self.ensure_category_state(guild, "events", opened=False, report=report, reason=reason)
        await self.ensure_category_state(guild, "voice", opened=False, report=report, reason=reason)
        await self.ensure_category_state(guild, "lecture", opened=False, report=report, reason=reason)
        await self.ensure_category_state(
            guild,
            "season_misc",
            opened=False,
            report=report,
            reason=reason,
            exclude_names=ALWAYS_OPEN_CHANNELS,
        )

        await self.ensure_study_text_channels(guild, opened=False, report=report, reason=reason)
        await self.ensure_study_voice_channels(
            guild,
            tuple(),
            opened=False,
            report=report,
            reason=reason,
        )

        # Keep these explicitly open as failsafes.
        for always_open in ALWAYS_OPEN_CHANNELS:
            await self.ensure_channel_state(guild, (always_open,), opened=True, report=report, reason=reason)

        return report

    async def apply_protocol(self, guild: nextcord.Guild, state: ProtocolState, reason: str) -> ActionReport:
        report = ActionReport()

        # 1) Always-open failsafes.
        for always_open in ALWAYS_OPEN_CHANNELS:
            await self.ensure_channel_state(guild, (always_open,), opened=True, report=report, reason=reason)

        # 2) Essential channels.
        for channel_name in ESSENTIAL_GENERAL_CHANNELS:
            await self.ensure_channel_state(
                guild,
                (channel_name,),
                opened=state.essential_open,
                report=report,
                reason=reason,
            )

        await self.ensure_category_state(
            guild,
            "lecture",
            opened=state.essential_open,
            report=report,
            reason=reason,
        )

        # 3) Non-essential channels / categories.
        for aliases in NONESSENTIAL_TEXT_CHANNEL_ALIASES.values():
            await self.ensure_channel_state(
                guild,
                aliases,
                opened=not state.nonessential_closed,
                report=report,
                reason=reason,
            )


        await self.ensure_category_state(
            guild,
            "lounge",
            opened=not state.nonessential_closed,
            report=report,
            reason=reason,
            exclude_names={"lounge-signup"},
        )
        await self.ensure_category_state(
            guild,
            "events",
            opened=not state.nonessential_closed,
            report=report,
            reason=reason,
        )
        await self.ensure_category_state(
            guild,
            "voice",
            opened=not state.nonessential_closed,
            report=report,
            reason=reason,
        )

        # 4) Subject channels.
        for subject in sorted(all_canonical_subjects()):
            await self.ensure_subject_state(
                guild,
                subject,
                opened=subject in state.open_subjects,
                report=report,
                reason=reason,
            )

        # 5) AP season misc category, excluding always-open failsafes.
        misc_open = state.essential_open
        await self.ensure_category_state(
            guild,
            "season_misc",
            opened=misc_open,
            report=report,
            reason=reason,
            exclude_names=ALWAYS_OPEN_CHANNELS,
        )

        # 6) Study rooms and study voice.
        study_open = len(state.study_subjects) > 0
        await self.ensure_study_text_channels(
            guild,
            opened=study_open,
            report=report,
            reason=reason,
        )
        await self.ensure_study_voice_channels(
            guild,
            state.study_subjects,
            opened=study_open,
            report=report,
            reason=reason,
        )

        return report