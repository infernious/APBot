"""Honey-pot with automatic warning and private evidence logging."""
import asyncio
from collections import OrderedDict
import logging
import io
import json
import re
from types import SimpleNamespace
import os
import time
from datetime import datetime, timezone

import nextcord
from nextcord.ext import commands
from models import Infraction

log = logging.getLogger(__name__)

# No channel IDs or config.json changes required.
HONEYPOT_ENABLED = True
HONEYPOT_DRY_RUN = False  # True disables all punishments on both identities.
CHANNEL_NAME = "honey-pot"
LOG_CHANNEL_NAME = "honey-pot-log"
BAN_REASON = "Talking in honeypot"
APPEAL_URL = "https://discord.gg/RHx7deYQ3q"
PRODUCTION_IDENTITY = (1464966749643341847, 181970867549503489)
TEST_IDENTITY = (1263186086260244520, 1498714554983645207)
STAFF_ROLES = frozenset({"admin", "administrator", "moderator", "chat moderator",
                         "lead moderator", "trial chat moderator", "trial moderator"})
LOG_ROLES = STAFF_ROLES | {"bot staff", "senior bot staff"}
STAFF_PERMISSIONS = ("administrator", "moderate_members", "ban_members", "kick_members", "manage_messages")
MAX_PENDING = 4
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_EVIDENCE_BYTES = 24 * 1024 * 1024
MAX_ATTACHMENTS = 10
EVIDENCE_TIMEOUT = 60
MAX_MESSAGE_AGE = 120
RECENT_BAN_LIMIT = 1024
NO_MENTIONS = nextcord.AllowedMentions.none()

ACTIVE_WARNING = (
    "# ⚠️ WARNING\n\n"
    "Do not send any messages in this channel.\n\n"
    "This channel is used to catch automated scam and spam accounts. "
    "Sending a message here will result in an automatic ban.\n\n"
    "**IF YOU ARE BANNED, IT MAY TAKE UP TO TWO WEEKS FOR YOU TO BE UNBANNED "
    "AFTER SUBMITTING AN APPEAL.**"
)
DRY_WARNING = (
    "# ⚠️ WARNING\n\nDo not send messages in this channel.\n\n"
    "This channel is used to catch automated scam and spam accounts. "
    "When enforcement is enabled, posting here will result in an automatic ban. "
    "The channel is currently in testing mode; no automatic bans are applied. "
    "Moderators, administrators and bots are exempt.\n\n"
    "Ban appeals have a 14-day review period."
)


def role_name(role):
    return str(getattr(role, "name", "")).casefold()


def staff(member, names=STAFF_ROLES):
    return (any(role_name(r) in names for r in getattr(member, "roles", ()))
            or any(getattr(getattr(member, "guild_permissions", None), p, False)
                   for p in STAFF_PERMISSIONS))


def exempt(member, guild):
    return (member is None or getattr(member, "bot", False)
            or member.id == guild.owner_id or staff(member))


def unique_channel(guild, name):
    matches = [c for c in guild.text_channels if c.name.casefold() == name]
    return matches[0] if len(matches) == 1 else None


def private_log(guild):
    channel = unique_channel(guild, LOG_CHANNEL_NAME)
    me = guild.me
    if channel is None or me is None:
        return None
    if channel.permissions_for(guild.default_role).view_channel:
        log.warning("Honey-pot log blocked: @everyone can view #%s", LOG_CHANNEL_NAME)
        return None
    roles = {r.id: r for r in guild.roles}
    own_roles = {r.id for r in me.roles if getattr(r, "managed", False)
                 and getattr(getattr(r, "tags", None), "bot_id", None) == me.id}
    for role in guild.roles:
        if role.id == guild.default_role.id or role.id in own_roles:
            continue
        if not channel.permissions_for(role).view_channel:
            continue
        if role_name(role) in LOG_ROLES or any(getattr(role.permissions, p, False) for p in STAFF_PERMISSIONS):
            continue
        log.warning("Honey-pot log blocked: non-staff role %r can view #%s", role.name, LOG_CHANNEL_NAME)
        return None
    for target, overwrite in channel.overwrites.items():
        if target.id in roles or overwrite.view_channel is not True:
            continue
        if target.id != me.id and not staff(target, LOG_ROLES):
            log.warning("Honey-pot log blocked: non-staff member/unknown overwrite %s", target.id)
            return None
    perms = channel.permissions_for(me)
    if not all(getattr(perms, p, False) for p in ("view_channel", "send_messages", "embed_links")):
        log.warning("Honey-pot log blocked: bot lacks View Channel, Send Messages or Embed Links")
        return None
    return channel


def message_is_recent(message):
    age = (datetime.now(timezone.utc) - message.created_at).total_seconds()
    return -5 <= age <= MAX_MESSAGE_AGE


def make_embed(message, state, evidence=()):
    embed = nextcord.Embed(title="Honey-pot", description=state,
                           color=0xED4245 if state.startswith("Member banned") else 0xF0B232,
                           timestamp=datetime.now(timezone.utc))
    embed.add_field(name="Member", value=f"<@{message.author.id}> (`{message.author.id}`)", inline=False)
    embed.add_field(name="Channel", value=f"<#{message.channel.id}>", inline=True)
    embed.add_field(name="Message ID", value=f"`{message.id}`", inline=False)
    # Escape user backticks; full original text is preserved in a file when needed.
    body = str(message.content or "").replace("`", "ˋ")[:800]
    if body:
        embed.add_field(name="Text", value=f"```\n{body}\n```", inline=False)
    embed.add_field(name="Attachments", value=str(len(message.attachments)), inline=True)
    for start in range(0, len(evidence), 6):
        embed.add_field(name="Evidence", value=" | ".join(
            f"[File {i}]({url})" for i, url in enumerate(evidence[start:start+6], start+1)), inline=False)
    return embed


def ban_dm_embed(bot, member, actiontime):
    # Match the user-facing /ban embed, without invoking its interaction/log side effects.
    embed = nextcord.Embed(title="Infraction: Ban", description=f"**Reason:**\n{BAN_REASON}",
                           color=getattr(bot, "colors", {}).get("red", 0xED4245),
                           timestamp=actiontime)
    name = getattr(member, "display_name", None) or getattr(member, "name", str(member.id))
    avatar = getattr(getattr(member, "display_avatar", None), "url", None)
    embed.set_author(name=name, icon_url=avatar)
    embed.add_field(name="Appeal", value="If you wish to appeal your ban, you may do so by joining the following server: " + APPEAL_URL,
                    inline=False)
    return embed


def snapshot_message(message):
    # Capture the original gateway content before any awaits; edits must not erase evidence.
    return SimpleNamespace(id=message.id, author=message.author, channel=message.channel,
                           created_at=message.created_at, jump_url=message.jump_url,
                           content=str(message.content or ""), attachments=tuple(message.attachments),
                           stickers=tuple(getattr(message, "stickers", ()) or ()),
                           embeds=tuple(getattr(message, "embeds", ()) or ()),
                           poll=getattr(message, "poll", None),
                           message_snapshots=tuple(getattr(message, "message_snapshots", ()) or ()))


async def archive_evidence(guild, review, message):
    """Upload original attachments separately, before the moderation embed or ban."""
    limit = min(MAX_ATTACHMENT_BYTES, getattr(guild, "filesize_limit", MAX_ATTACHMENT_BYTES))
    attachments = message.attachments
    if (len(attachments) > MAX_ATTACHMENTS or any(a.size < 0 or a.size > limit for a in attachments)
            or sum(a.size for a in attachments) > MAX_EVIDENCE_BYTES):
        raise ValueError("Evidence exceeds safe attachment budget")
    files = []
    if len(message.content) > 800 or "`" in message.content:
        files.append(("original-message.txt", message.content.encode("utf-8")))
    # For non-attachment Discord objects preserve metadata, not externally hosted media.
    meta = {}
    if message.stickers:
        meta["stickers"] = [{"id": str(x.id), "name": str(x.name)} for x in message.stickers]
    if message.embeds:
        meta["embeds"] = [x.to_dict() for x in message.embeds]
    if message.poll is not None:
        meta["poll"] = {"question": str(getattr(message.poll, "question", "")),
                        "answers": [str(getattr(x, "text", "")) for x in getattr(message.poll, "answers", ())]}
    if message.message_snapshots:
        meta["forwarded"] = [{"content": str(getattr(x, "content", "")),
                              "attachments": [{"id": str(a.id), "filename": str(a.filename), "size": a.size}
                                              for a in getattr(x, "attachments", ())]}
                             for x in message.message_snapshots]
    if meta:
        files.append(("message-metadata.json", json.dumps(meta, ensure_ascii=False, default=str).encode("utf-8")))
    if any(len(data) > limit for _, data in files):
        raise ValueError("Evidence metadata exceeds upload limit")
    if (attachments or files) and not review.permissions_for(guild.me).attach_files:
        raise PermissionError("Honey-pot log requires Attach Files")
    links = []

    async def upload(name, data):
        if private_log(guild) is not review or not review.permissions_for(guild.me).attach_files:
            raise PermissionError("Honey-pot log permissions changed")
        f = nextcord.File(io.BytesIO(data), filename=name)
        try:
            sent = await review.send(file=f, allowed_mentions=NO_MENTIONS)
            links.append(sent.jump_url)
        finally:
            f.close()

    for name, data in files:
        await upload(f"evidence-{message.id}-{name}", data)
    for index, attachment in enumerate(attachments, 1):
        # Discord's own attachment API; no arbitrary URLs are fetched.
        try:
            data = await attachment.read()
        except nextcord.NotFound:
            data = await attachment.read(use_cached=True)
        if len(data) != attachment.size or len(data) > limit:
            raise ValueError("Attachment size changed or exceeded limit")
        filename = re.sub(r"[^A-Za-z0-9._-]", "_", str(attachment.filename))[-100:]
        await upload(f"evidence-{message.id}-{index}-{filename or 'attachment'}", data)
    return links


class Honeypot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pending = set()
        self.recent_bans = OrderedDict()
        self.notice_lock = asyncio.Lock()
        self.notice = None
        self.evidence_lock = asyncio.Lock()

    def mode(self, guild):
        """Only configured bot/guild pairs; test bans require the test DB environment."""
        if not HONEYPOT_ENABLED or getattr(guild, "unavailable", False):
            return None
        try:
            identity = (self.bot.user.id, guild.id)
            if int(self.bot.config.get("guild_id")) != guild.id:
                return None
            if int(self.bot.config.get("application_id")) != identity[0]:
                return None
        except (AttributeError, TypeError, ValueError):
            return None
        if identity == TEST_IDENTITY:
            if os.environ.get("APBOT_DATABASE_NAME") != "ap-test":
                return None
        elif identity == PRODUCTION_IDENTITY:
            if os.environ.get("APBOT_DATABASE_NAME", "ap-students") != "ap-students":
                return None
        else:
            return None
        return "dry-run" if HONEYPOT_DRY_RUN else "enforce"

    def warning(self, mode):
        return ACTIVE_WARNING if mode == "enforce" else DRY_WARNING

    def own_warning(self, message, mode):
        return (message.author.id == self.bot.user.id
                and not getattr(message, "webhook_id", None)
                and message.content == self.warning(mode))

    async def find_warning(self, channel, mode):
        # Remember the warning ID so ordinary chat cannot push it out of the history window.
        if self.notice is not None and self.notice[:2] == (channel.id, mode):
            try:
                m = await channel.fetch_message(self.notice[2])
            except nextcord.NotFound:
                m = None
            if m is not None and self.own_warning(m, mode):
                return m
            self.notice = None
        async for m in channel.history(limit=50):
            if self.own_warning(m, mode):
                self.notice = (channel.id, mode, m.id)
                return m
        return None

    async def armed(self, channel, mode, before_id):
        """The current bot-authored warning must exist and predate the trigger; no pin required."""
        async with self.notice_lock:
            m = await self.find_warning(channel, mode)
            return m is not None and m.id < before_id

    @commands.Cog.listener()
    async def on_ready(self):
        async with self.notice_lock:
            try:
                guild = self.bot.get_guild(int(self.bot.config.get("guild_id")))
                mode = self.mode(guild)
                if mode is None:
                    return
                channel = unique_channel(guild, CHANNEL_NAME)
                if channel is None:
                    return
                if await self.find_warning(channel, mode) is None:
                    m = await channel.send(self.warning(mode), allowed_mentions=NO_MENTIONS)
                    self.notice = (channel.id, mode, m.id)
                log.info("Honey-pot: warning available in #%s (%s); pinning optional", CHANNEL_NAME, mode)
            except Exception:
                log.exception("Honey-pot warning setup failed; no ban without a current warning")

    async def valid_member(self, guild, message, mode):
        member = await guild.fetch_member(message.author.id)
        if exempt(member, guild):
            return None
        if getattr(member, "joined_at", None) and member.joined_at > message.created_at:
            return None  # stale message from a prior membership
        if mode == "enforce":
            me = guild.me
            if me is None or not me.guild_permissions.ban_members or me.top_role <= member.top_role:
                log.warning("Honey-pot cannot ban member=%s: permission or role hierarchy", member.id)
                return None
        return member

    @commands.Cog.listener()
    async def on_message(self, message):
        guild = message.guild
        mode = self.mode(guild)
        if mode is None or getattr(message, "webhook_id", None):
            return
        if message.type not in (nextcord.MessageType.default, nextcord.MessageType.reply):
            return
        if str(getattr(message.channel, "name", "")).casefold() != CHANNEL_NAME:
            return
        channel = unique_channel(guild, CHANNEL_NAME)
        if channel is None or channel.id != message.channel.id or exempt(message.author, guild):
            return
        if not getattr(getattr(self.bot, "intents", None), "message_content", False):
            log.warning("Honey-pot disabled for message=%s: message-content intent required for evidence", message.id)
            return
        if not message_is_recent(message):
            return
        key = (guild.id, message.author.id)
        now = time.monotonic()
        while self.recent_bans and next(iter(self.recent_bans.values())) <= now:
            self.recent_bans.popitem(last=False)
        if key in self.pending or key in self.recent_bans:
            return
        if len(self.pending) >= MAX_PENDING:
            log.warning("Honey-pot overloaded: message=%s skipped", message.id)
            return
        self.pending.add(key)
        try:
            await self.process(message, guild, channel, mode, snapshot_message(message))
        except nextcord.NotFound:
            log.warning("Honey-pot message or member disappeared: message=%s", message.id)
        except Exception:
            log.exception("Honey-pot processing failed: message=%s", message.id)
        finally:
            self.pending.discard(key)

    async def process(self, message, guild, channel, mode, original):
        if not await self.armed(channel, mode, message.id):
            log.warning("Honey-pot ignored message=%s: bot's current warning unavailable", message.id)
            return
        review = private_log(guild)
        if review is None:
            return
        member = await self.valid_member(guild, message, mode)
        if member is None:
            return
        try:
            current = await channel.fetch_message(message.id)
        except nextcord.NotFound:
            current = message  # Posting, not continued visibility, is the trigger.
        if current.author.id != member.id or not message_is_recent(current):
            return
        # Keep each evidence group together under concurrent posts.
        async with self.evidence_lock:
            if not message_is_recent(original) or private_log(guild) is not review:
                return
            # Preserve the original event, not a later edited version.
            try:
                evidence = await asyncio.wait_for(archive_evidence(guild, review, original), EVIDENCE_TIMEOUT)
            except Exception:
                log.exception("Honey-pot evidence upload failed; no ban: message=%s", original.id)
                return
            if private_log(guild) is not review:
                return
            if mode == "dry-run":
                await review.send(embed=make_embed(original, "Dry-run: member would be banned. No action taken.", evidence=evidence),
                                  allowed_mentions=NO_MENTIONS)
                return
            entry = await review.send(embed=make_embed(original, "Ban pending", evidence=evidence), allowed_mentions=NO_MENTIONS)
        # Recheck after the log send: permissions, staff roles, notice, and message may change.
        result = "Cancelled: safety check failed"
        detail = "No ban applied."
        try:
            if (self.mode(guild) != "enforce" or unique_channel(guild, CHANNEL_NAME) is not channel
                    or private_log(guild) is not review or not await self.armed(channel, mode, current.id)):
                return
            member = await self.valid_member(guild, current, mode)
            if member is None or not message_is_recent(current):
                return
            try:
                latest = await channel.fetch_message(current.id)
            except nextcord.NotFound:
                latest = current
            if latest.author.id != member.id:
                return
            try:
                await guild.ban(member, reason=BAN_REASON, delete_message_seconds=0)
            except Exception:
                result = "Ban failed or unconfirmed"
                detail = "Check Discord's audit log. No further action was taken."
                log.exception("Honey-pot ban failed or unconfirmed: member=%s", member.id)
                return
            result = "Member banned"
            key = (guild.id, member.id)
            self.recent_bans[key] = time.monotonic() + MAX_MESSAGE_AGE
            self.recent_bans.move_to_end(key)
            while len(self.recent_bans) > RECENT_BAN_LIMIT:
                self.recent_bans.popitem(last=False)
            outcomes = []
            actiontime = datetime.now(timezone.utc)
            try:
                infraction = Infraction(actiontype="ban", reason=BAN_REASON, moderator=self.bot.user.id,
                                        actiontime=actiontime, duration=None, attachment_url=None)
                await asyncio.wait_for(self.bot.db.base_db.add_infraction(member.id, infraction), 10)
                outcomes.append("Infraction recorded")
            except Exception:
                log.exception("Honey-pot ban recorded in Discord but database write failed or unconfirmed: member=%s", member.id)
                outcomes.append("Infraction write failed or unconfirmed; check manually")
            try:
                await latest.delete()
                outcomes.append("Trigger message deleted")
            except nextcord.NotFound:
                outcomes.append("Trigger message already gone")
            except Exception:
                log.exception("Honey-pot banned member but could not delete trigger: message=%s", latest.id)
                outcomes.append("Trigger message deletion failed")
            try:
                await asyncio.wait_for(member.send(embed=ban_dm_embed(self.bot, member, actiontime),
                                                  allowed_mentions=NO_MENTIONS), 10)
                outcomes.append("DM sent")
            except Exception:
                outcomes.append("DM failed or unconfirmed")
            detail = "; ".join(outcomes)
        finally:
            log.warning("Honey-pot outcome: member=%s message=%s status=%s detail=%s",
                        original.author.id, original.id, result, detail)
            try:
                await entry.edit(embed=make_embed(original, result, evidence=evidence), allowed_mentions=NO_MENTIONS)
            except Exception:
                log.exception("Honey-pot could not update log: message=%s result=%s", current.id, result)


def setup(bot):
    bot.add_cog(Honeypot(bot))
