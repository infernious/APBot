"""Pure policy functions; no Discord or database dependency."""
from dataclasses import dataclass
import math

PROD_REVIEW = 14 * 86400
PROD_REMINDER = 2 * 86400
PROD_COOLDOWN = 84 * 86400
TEST_DATABASE = "ap-test"

# Edit these values for local appeal testing only. Units: seconds.
TEST_REVIEW = 5 * 60
TEST_REMINDER = 2 * 60  # Time remaining before the decision.
TEST_COOLDOWN = 5 * 60  # Time after rejection.
TEST_MAX_VOTES = 3
# Independent safety allowlist for the existing local test bot and main guild.
# These are NOT production settings or additional config keys.
TEST_BOT_ID = 1263186086260244520
TEST_MAIN_GUILD_ID = 1498714554983645207
STAFF_ROLE_NAMES = frozenset({"Trial Chat Moderator", "Chat Moderator", "Moderator", "Admin", "Lead Moderator"})
PING_ROLE_NAMES = ("Moderator", "Chat Moderator")


def moderator_role(guild):
    for name in PING_ROLE_NAMES:
        matches = [r for r in guild.roles if r.name == name and r.id != guild.id]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous {name} role; appeal processing disabled")
        if matches:
            return matches[0]
    raise RuntimeError("No Moderator or Chat Moderator role found")


def eligible_voter(member):
    return member.guild_permissions.administrator or any(r.name in STAFF_ROLE_NAMES for r in member.roles)


def positive_int(value, name, minimum=1, maximum=10**10):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid appeal setting {name}: expected integer {minimum}..{maximum}")
    return value


@dataclass(frozen=True)
class AppealPolicy:
    review: int
    reminder: int
    cooldown: int
    max_votes: int
    testing: bool
    poll: int
    application_id: int

    @classmethod
    def load(cls, config, database_name):
        if database_name not in (TEST_DATABASE, "ap-students"):
            raise ValueError("Unsupported appeal database")
        testing = database_name == TEST_DATABASE
        main = positive_int(config.get("guild_id"), "guild_id", 1, 2**64-1)
        appeal = positive_int(config.get("ban_appeal_server"), "ban_appeal_server", 1, 2**64-1)
        channel = positive_int(config.get("appeals_channel_id"), "appeals_channel_id", 1, 2**64-1)
        app = positive_int(config.get("application_id"), "application_id", 1, 2**64-1)
        if main == appeal:
            raise ValueError("Distinct main and appeal servers required")
        if testing and (main != TEST_MAIN_GUILD_ID or app != TEST_BOT_ID):
            raise ValueError("Accelerated appeals require the known local test bot and main guild")
        if not testing and (main == TEST_MAIN_GUILD_ID or app == TEST_BOT_ID):
            raise ValueError("The local test bot/guild must not use the production database")
        review = positive_int(TEST_REVIEW if testing else PROD_REVIEW, "review duration")
        reminder = positive_int(TEST_REMINDER if testing else PROD_REMINDER, "reminder lead time")
        cooldown = positive_int(TEST_COOLDOWN if testing else PROD_COOLDOWN, "reappeal cooldown")
        max_votes = positive_int(TEST_MAX_VOTES if testing else 3, "reminder vote threshold", 0, 100)
        if reminder >= review:
            raise ValueError("Reminder lead time must be shorter than review duration")
        if not testing and (review < 14*86400 or cooldown < 84*86400):
            raise ValueError("Production review/cooldown cannot be accelerated")
        return cls(review, reminder, cooldown, max_votes, testing, 5 if testing else 60, app)

    def snapshot(self, now):
        return {"deadline_at": now + self.review, "reminder_at": now + self.review - self.reminder,
                "cooldown_seconds": self.cooldown, "reminder_max_votes": self.max_votes}


def deadline(record):
    return record.get("deadline_at", record["submission_time"] + PROD_REVIEW)


def reminder_at(record):
    return record.get("reminder_at", deadline(record) - PROD_REMINDER)


def reappeal_at(record):
    if record.get("decision") is not False:
        return None
    return record.get("reappeal_at", record["submission_time"] + PROD_COOLDOWN)


def reminder_due(record, now, voters):
    return (record.get("decision") is None and not record.get("reminder_checked_at") and not record.get("reminder_claimed_at")
            and reminder_at(record) <= now < deadline(record)
            and voters <= record.get("reminder_max_votes", 3))


def vote_result(green, red, yellow):
    """One person, one vote. Conflicting red/green votes are abstentions."""
    conflict = green & red
    return len(green - conflict) > len(red - conflict), len(green | red | yellow)


def duration_text(seconds):
    seconds = max(0, math.ceil(seconds))
    for unit, size in (("week", 604800), ("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size and seconds % size == 0:
            n = seconds // size
            return f"{n} {unit}{'s' if n != 1 else ''}"
    return f"{seconds} second{'s' if seconds != 1 else ''}"


def previous_appeals(record, channel_id, limit=20):
    prior = [dict(x) for x in record.get("previous_appeals", []) if isinstance(x, dict) and x.get("message_id")]
    if record.get("message_id") and all(x["message_id"] != record["message_id"] for x in prior):
        prior.append({"message_id": record["message_id"], "channel_id": record.get("channel_id", channel_id),
                      "decision": record.get("decision")})
    return prior[-limit:]
