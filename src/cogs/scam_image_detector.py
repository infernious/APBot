"""Targeted casino-scam moderation. One bounded queue, one local OCR process."""
from __future__ import annotations
import asyncio
import hashlib
from io import BytesIO
import logging
import os
from pathlib import Path
import struct
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from collections import OrderedDict

import nextcord
from nextcord.ext import commands
from utils.scam_rules import Match, classify_image_text, image_match, report_context

log = logging.getLogger(__name__)
# Local settings: change these here; restart the bot to apply.
# Existing explicit config.json values override these defaults (remove those
# keys if you prefer to control the detector entirely from this file).
SCAM_DETECTOR_ENABLED = True
SCAM_DETECTOR_DRY_RUN = True
# Automatically enter review-only staff testing on the designated test bot.
# This does not enable staff scanning on the production bot.
SCAM_DETECTOR_TEST_MODE = True
REVIEW_CHANNEL_NAME = "automod-bot"
# Exact names, not substring matches; independent of server-specific role IDs.
MODERATION_BYPASS_ROLE_NAMES = frozenset({
    "admin", "moderator", "chat moderator", "lead moderator", "trial chat moderator",
})
# Evidence access is separate from punishment immunity.
REVIEW_ACCESS_ROLE_NAMES = MODERATION_BYPASS_ROLE_NAMES | frozenset({
    "bot staff", "senior bot staff",
})


IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
MAX_SCAN_BYTES = 8 * 1024 * 1024
MAX_ATTACHMENTS = 6
QUEUE_SIZE = 8
OCR_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 10
REST_TIMEOUT = 10
IDLE_TIMEOUT = 60
MAX_AGE = 120
SCAN_BUDGET = 45
CACHE_SIZE = 256
SCAM_TIMEOUT = timedelta(days=7)
# Queued copies of one scam burst must not repeatedly extend the same timeout.
TIMEOUT_TOLERANCE = timedelta(minutes=5)
SCAM_REASON = "Scam"
TEST_BOT_ID = 1263186086260244520
TEST_GUILD_ID = 1498714554983645207


def staff(member):
    p = getattr(member, 'guild_permissions', None)
    return bool(getattr(p, 'administrator', False) or getattr(p, 'manage_messages', False) or any(str(getattr(r, 'name', '')).casefold() in MODERATION_BYPASS_ROLE_NAMES for r in getattr(member, 'roles', ())))


def review_staff(member):
    return staff(member) or any(
        str(getattr(role, "name", "")).casefold() in REVIEW_ACCESS_ROLE_NAMES
        for role in getattr(member, "roles", ())
    )


def is_visual_attachment(a):
    mime = (getattr(a, 'content_type', '') or '').split(';')[0].lower()
    return (mime in {'image/png','image/jpeg','image/webp','image/bmp','image/x-ms-bmp'} or (not mime and Path(getattr(a, 'filename', '') or '').suffix.lower() in IMAGE_EXTENSIONS)) and 0 < (getattr(a, 'size', 0) or 0) <= MAX_SCAN_BYTES


def signature(m):
    return (m.content or '', tuple((a.id, a.size, a.filename) for a in m.attachments))


class OCRProcess:
    def __init__(self):
        self.proc = None
        self.retry_at = 0

    async def stop(self):
        p, self.proc = self.proc, None
        if p is not None:
            if p.returncode is None:
                try: p.kill()
                except ProcessLookupError: pass
            await p.wait()

    async def _exchange(self, data):
        if self.proc is None or self.proc.returncode is not None:
            await self.stop()
            env = dict(os.environ)
            for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
                env[k] = '1'
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(sys.executable, '-u', '-m', 'utils.scam_ocr_worker', cwd=str(Path(__file__).resolve().parents[1]), env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE))
            try:
                self.proc = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                # Recover the process handle even if cancellation arrives during creation.
                self.proc = await spawn
                await self.stop()
                raise
        p = self.proc
        p.stdin.write(struct.pack('!I', len(data)) + data)
        await p.stdin.drain()
        n = struct.unpack('!I', await p.stdout.readexactly(4))[0]
        if not 1 <= n <= 24001:
            raise ValueError('invalid OCR response length')
        response = await p.stdout.readexactly(n)
        if response == b'\x02':
            return Match('near-identical known campaign screenshot')
        if response[0] != 0:
            raise RuntimeError('OCR worker failed: ' + response[1:].decode('ascii','replace')[:128])
        return response[1:].decode('utf-8', 'replace')

    async def scan(self, data):
        if time.monotonic() < self.retry_at:
            return None
        try:
            return await asyncio.wait_for(self._exchange(data), OCR_TIMEOUT)
        except asyncio.CancelledError:
            await self.stop()
            raise
        except Exception as exc:
            log.warning('Scam OCR unavailable: %s', type(exc).__name__)
            await self.stop()
            self.retry_at = time.monotonic() + 30
            return None


@dataclass(frozen=True)
class Job:
    guild_id: int
    channel_id: int
    message_id: int
    created: float


class ScamImageDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = asyncio.Queue(QUEUE_SIZE)
        self.pending = set()
        self.dirty = set()
        self.task = None
        self.ocr = OCRProcess()
        self.closed = False
        self.last_overload = -float('inf')
        self.skipped = 0
        self.cache = OrderedDict()

    def cog_unload(self):
        self.closed = True
        if self.task is not None:
            self.task.cancel()

    def config(self, key, default=None):
        defaults = {
            'scam_detector_enabled': SCAM_DETECTOR_ENABLED,
            'scam_detector_dry_run': SCAM_DETECTOR_DRY_RUN,
            'scam_detector_test_mode': SCAM_DETECTOR_TEST_MODE and getattr(getattr(self.bot, 'user', None), 'id', None) == TEST_BOT_ID,
        }
        return self.bot.config.get(key, defaults.get(key, default))

    def test_mode(self):
        return self.config('scam_detector_test_mode', False) is True

    def in_scope(self, guild_id, channel_id):
        try:
            bot_id = self.bot.user.id
            if self.test_mode() and (bot_id != TEST_BOT_ID or guild_id != TEST_GUILD_ID):
                return False
            application = int(self.config('application_id', bot_id))
            if self.closed or self.config('scam_detector_enabled', True) is not True or bot_id != application or guild_id != int(self.config('guild_id')):
                return False
            channel = self.bot.get_channel(channel_id)
            return str(getattr(channel, 'name', '')).casefold() != REVIEW_CHANNEL_NAME.casefold()
        except (AttributeError, TypeError, ValueError):
            return False

    def eligible(self, m):
        return bool(m.guild and self.in_scope(m.guild.id, m.channel.id) and not m.author.bot and (self.test_mode() or not staff(m.author)) and isinstance(m.author, nextcord.Member))

    def enqueue(self, guild_id, channel_id, message_id, *, edited=False):
        if not self.in_scope(guild_id, channel_id):
            return
        key = (channel_id, message_id)
        if key in self.pending:
            if edited: self.dirty.add(key)
            return
        try:
            self.queue.put_nowait(Job(guild_id, channel_id, message_id, time.monotonic()))
        except asyncio.QueueFull:
            self.skipped += 1
            now = time.monotonic()
            if now - self.last_overload >= 60:
                log.warning('Scam scanner overloaded; skipped=%s (fail open)', self.skipped)
                self.last_overload = now
            return
        self.pending.add(key)
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.eligible(message) and any(is_visual_attachment(a) for a in message.attachments):
            self.enqueue(message.guild.id, message.channel.id, message.id)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        if not self.in_scope(payload.guild_id, payload.channel_id):
            return
        data = payload.data
        if 'content' not in data and 'attachments' not in data:
            return
        key = (payload.channel_id, payload.message_id)
        cached = getattr(payload, 'cached_message', None)
        raw_images = any(is_visual_attachment(SimpleNamespace(**{k: a.get(k) for k in ('filename', 'content_type', 'size')}))
                         for a in (data.get('attachments') or []) if isinstance(a, dict))
        if key in self.pending or raw_images or (cached and self.eligible(cached) and any(is_visual_attachment(a) for a in cached.attachments)):
            self.enqueue(payload.guild_id, payload.channel_id, payload.message_id, edited=True)

    async def run(self):
        try:
            while not self.closed:
                try:
                    job = await asyncio.wait_for(self.queue.get(), IDLE_TIMEOUT)
                except asyncio.TimeoutError:
                    await self.ocr.stop()
                    continue
                key = (job.channel_id, job.message_id)
                try:
                    if time.monotonic() - job.created <= MAX_AGE:
                        await self.process(job)
                    else:
                        log.warning('Scam scan expired: message=%s', job.message_id)
                except nextcord.NotFound:
                    pass
                except Exception as exc:
                    log.warning('Scam scan failed: message=%s error=%s', job.message_id, type(exc).__name__)
                finally:
                    self.pending.discard(key)
                    changed = key in self.dirty
                    self.dirty.discard(key)
                    self.queue.task_done()
                    if changed and not self.closed:
                        self.enqueue(job.guild_id, job.channel_id, job.message_id)
        finally:
            await self.ocr.stop()

    async def fetch(self, job):
        channel = self.bot.get_channel(job.channel_id)
        if channel is None:
            return None
        if getattr(getattr(channel, 'guild', None), 'id', None) != job.guild_id:
            return None
        return await asyncio.wait_for(channel.fetch_message(job.message_id), REST_TIMEOUT)

    async def assess(self, message, *, evidence=None, all_matches=False):
        first = (None, None)
        # Scan images independently: unrelated text in multiple pictures cannot combine into a match.
        for a in [a for a in message.attachments if is_visual_attachment(a)][:MAX_ATTACHMENTS]:
            try:
                data = await asyncio.wait_for(a.read(), DOWNLOAD_TIMEOUT)
            except (nextcord.HTTPException, asyncio.TimeoutError):
                continue
            if not 0 < len(data) <= MAX_SCAN_BYTES:
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest in self.cache:
                result = self.cache[digest]
                self.cache.move_to_end(digest)
            else:
                result = image_match(data)
                if result is None:
                    text = await self.ocr.scan(data)
                    if text is None:
                        continue  # Never cache an OCR failure as a clean result.
                    result = text if isinstance(text, Match) else classify_image_text(text)
                self.cache[digest] = result
                if len(self.cache) > CACHE_SIZE:
                    self.cache.popitem(last=False)
            if result:
                if evidence is not None:
                    suffix = Path(a.filename or "").suffix.lower()
                    if suffix not in IMAGE_EXTENSIONS:
                        suffix = {"image/jpeg": ".jpg", "image/webp": ".webp", "image/bmp": ".bmp", "image/x-ms-bmp": ".bmp"}.get((a.content_type or "").split(";")[0].lower(), ".png")
                    evidence.append((data, suffix))
                if first[0] is None:
                    first = (result, digest)
                if not all_matches:
                    return first
        return first

    def private_review(self, guild):
        try:
            # Cache-only lookup in the source guild. Refuse ambiguous destinations.
            candidates = [ch for ch in guild.text_channels
                          if isinstance(ch, nextcord.TextChannel)
                          and ch.guild.id == guild.id
                          and ch.name.casefold() == REVIEW_CHANNEL_NAME.casefold()]
            if len(candidates) != 1:
                log.warning("Scam review blocked: expected one #%s, found %s", REVIEW_CHANNEL_NAME, len(candidates))
                return None
            channel = candidates[0]
            if channel.permissions_for(guild.default_role).view_channel:
                log.warning("Scam review blocked: @everyone can view #%s", channel.name)
                return None
            me = guild.me
            p = channel.permissions_for(me)
            if not (p.view_channel and p.send_messages and p.embed_links and p.attach_files):
                missing = [name for name in ("view_channel", "send_messages", "embed_links", "attach_files") if not getattr(p, name, False)]
                log.warning("Scam review blocked: bot missing %s in #%s", ", ".join(missing), channel.name)
                return None
            bot_roles = {r.id for r in me.roles if r.is_bot_managed()}
            for role in guild.roles:
                if role.id in bot_roles or role.name.casefold() in REVIEW_ACCESS_ROLE_NAMES:
                    continue
                if not (role.permissions.administrator or role.permissions.manage_messages) and channel.permissions_for(role).view_channel:
                    log.warning("Scam review blocked: non-exempt role %r (%s) can view #%s", role.name, role.id, channel.name)
                    return None
            for target, overwrite in channel.overwrites.items():
                if overwrite.view_channel is True and isinstance(target, nextcord.Member) and target.id != me.id and not review_staff(target):
                    log.warning("Scam review blocked: non-staff member overwrite (%s) in #%s", target.id, channel.name)
                    return None
                if overwrite.view_channel is True and not isinstance(target, (nextcord.Member, nextcord.Role)):
                    log.warning("Scam review blocked: unresolved overwrite in #%s", channel.name)
                    return None
            return channel
        except (AttributeError, ValueError, TypeError) as exc:
            log.warning("Scam review blocked: permission check error: %s", exc)
            return None

    async def timeout_sender(self, message):
        """Apply a native Discord timeout, never a ban or an infraction-point mute."""
        guild = message.guild
        if self.test_mode() or not self.eligible(message) or self.config('scam_detector_dry_run', True) is not False:
            return 'Skipped: enforcement disabled or exemption applies'
        try:
            me = guild.me
            if not getattr(getattr(me, 'guild_permissions', None), 'moderate_members', False):
                return 'Skipped: bot lacks Moderate Members'
            member = await asyncio.wait_for(guild.fetch_member(message.author.id), REST_TIMEOUT)
            if not isinstance(member, nextcord.Member) or member.id != message.author.id:
                return 'Skipped: member could not be verified'
            if member.bot or staff(member) or member.id == guild.owner_id or member.id == me.id:
                return 'Skipped: staff or protected member'
            if not me.top_role > member.top_role:
                return 'Skipped: role hierarchy'
            if not self.in_scope(guild.id, message.channel.id) or self.config('scam_detector_dry_run', True) is not False or self.private_review(guild) is None:
                return 'Skipped: enforcement disabled or audit unavailable'
            until = datetime.now(timezone.utc) + SCAM_TIMEOUT
            existing = member.communication_disabled_until
            if existing is not None and existing >= until - TIMEOUT_TOLERANCE:
                return 'Preserved existing timeout (at least approximately seven days remaining)'
            await asyncio.wait_for(member.timeout(timeout=until, reason=SCAM_REASON), REST_TIMEOUT)
            return f'Applied 7-day timeout (Scam), expires <t:{int(until.timestamp())}:F>'
        except nextcord.NotFound:
            return 'Skipped: member no longer available'
        except (nextcord.HTTPException, asyncio.TimeoutError):
            return 'Failed or unconfirmed: check Discord audit log'
        except (AttributeError, TypeError, ValueError):
            return 'Skipped: unable to verify timeout eligibility'

    async def post_test_review(self, message, job, evidence):
        # This path can never punish, even if dry_run is accidentally false.
        if not self.test_mode() or not self.in_scope(job.guild_id, job.channel_id):
            return
        channel = self.private_review(message.guild)
        if channel is None or not getattr(channel.permissions_for(message.guild.me), 'attach_files', False):
            log.warning('Scam test match: review channel unavailable or missing Attach Files: message=%s matches=%s', job.message_id, len(evidence))
            return
        # Group normal-sized images as the legacy detector did. Large batches
        # are split to cap each upload at the existing per-image byte budget.
        batches = []
        batch, size = [], 0
        for index, (image, suffix) in enumerate(evidence, 1):
            if batch and size + len(image) > MAX_SCAN_BYTES:
                batches.append(batch)
                batch, size = [], 0
            batch.append((index, image, suffix))
            size += len(image)
        if batch:
            batches.append(batch)
        for batch in batches:
            if not self.test_mode() or not self.in_scope(job.guild_id, job.channel_id) or self.private_review(message.guild) is not channel:
                return
            embed = nextcord.Embed(title='Scam Detected', description='Test mode: no action taken.', color=0xED4245)
            embed.add_field(name='Member', value=f'<@{message.author.id}> (`{message.author.id}`)', inline=False)
            embed.add_field(name='Channel', value=f'<#{job.channel_id}>', inline=True)
            embed.add_field(name='Reason', value=SCAM_REASON, inline=True)
            embed.add_field(name='Message', value=f'[Jump to message](https://discord.com/channels/{job.guild_id}/{job.channel_id}/{job.message_id})', inline=False)
            embed.add_field(name='Images', value=f'{len(batch)} of {len(evidence)} matches', inline=False)
            files = []
            try:
                for index, image, suffix in batch:
                    files.append(nextcord.File(BytesIO(image), filename=f'scam-{job.message_id}-{index}{suffix}'))
                uploaded = await asyncio.wait_for(channel.send(files=files, allowed_mentions=nextcord.AllowedMentions.none()), REST_TIMEOUT)
                if not self.test_mode() or not self.in_scope(job.guild_id, job.channel_id) or self.private_review(message.guild) is not channel:
                    return
                evidence_url = getattr(uploaded, 'jump_url', None)
                if isinstance(evidence_url, str) and evidence_url:
                    embed.add_field(name='Evidence', value=f'[View images]({evidence_url})', inline=False)
                await asyncio.wait_for(channel.send(embed=embed, allowed_mentions=nextcord.AllowedMentions.none()), REST_TIMEOUT)
            except (nextcord.HTTPException, asyncio.TimeoutError):
                log.warning('Scam test evidence upload failed: message=%s', job.message_id)
            finally:
                for file in files:
                    file.close()
        log.warning('Scam test matched: message=%s images=%s (no action)', job.message_id, len(evidence))

    async def process(self, job):
        m = await self.fetch(job)
        if m is None or not self.eligible(m) or not any(is_visual_attachment(a) for a in m.attachments):
            return
        before = signature(m)
        evidence = []
        testing = self.test_mode()
        if testing:
            # Collect all confirmed images, not just the first, for test review.
            try:
                match, digest = await asyncio.wait_for(self.assess(m, evidence=evidence, all_matches=True), SCAN_BUDGET)
            except asyncio.TimeoutError:
                log.warning('Scam test scan budget exhausted: message=%s', job.message_id)
            if evidence:
                await self.post_test_review(m, job, evidence)
            return
        match, digest = await asyncio.wait_for(self.assess(m, evidence=evidence), SCAN_BUDGET)
        if match is None:
            return
        dry = self.config('scam_detector_dry_run', True) is not False
        review_only = not match.delete or report_context(m.content)
        if dry or review_only:
            log.warning('Scam %s: guild=%s channel=%s message=%s reason=%s', 'dry-run would remove and timeout for 7 days (Scam)' if dry and not review_only else 'review only', job.guild_id, job.channel_id, job.message_id, match.reason)
            return
        # A private audit destination must be available before enforcement.
        channel = self.private_review(m.guild)
        if channel is None:
            log.warning('Scam matched but private review channel unavailable: message=%s', job.message_id)
            return
        if not evidence:
            log.warning('Scam matched but evidence unavailable: message=%s', job.message_id)
            return
        image, suffix = evidence[0]
        embed = nextcord.Embed(title='Scam Detected', description='Action pending', color=0xED4245)
        embed.add_field(name='Member', value=f'<@{m.author.id}> (`{m.author.id}`)', inline=False)
        embed.add_field(name='Channel', value=f'<#{job.channel_id}>', inline=False)
        embed.add_field(name='Message ID', value=str(job.message_id), inline=False)
        embed.add_field(name='Reason', value=SCAM_REASON, inline=False)
        embed.add_field(name='Evidence', value={
            'known campaign screenshot': 'Known casino scam image',
            'near-identical known campaign screenshot': 'Known casino scam image (modified copy)',
            'celebrity crypto-casino promotion': 'Celebrity casino scam image',
            'known casino payout/bonus screenshot': 'Casino payout or bonus scam image',
        }.get(match.reason, 'Scam image'), inline=False)
        # Upload the exact bytes used for the verdict before the original disappears.
        file = nextcord.File(BytesIO(image), filename=f'scam-{job.message_id}{suffix}')
        try:
            uploaded = await asyncio.wait_for(channel.send(file=file, allowed_mentions=nextcord.AllowedMentions.none()), REST_TIMEOUT)
        finally:
            file.close()
        if self.test_mode() or not self.eligible(m) or self.config('scam_detector_dry_run', True) is not False or self.private_review(m.guild) is not channel:
            return
        evidence_url = getattr(uploaded, 'jump_url', None)
        if isinstance(evidence_url, str) and evidence_url:
            embed.add_field(name='Image', value=f'[View image]({evidence_url})', inline=False)
        audit = await asyncio.wait_for(channel.send(embed=embed, allowed_mentions=nextcord.AllowedMentions.none()), REST_TIMEOUT)
        # Re-fetch after audit send. Never delete a changed message on stale evidence.
        outcome = 'Skipped: message changed or exemption applies'
        timeout_outcome = 'Not attempted: deletion not confirmed'
        try:
            fresh = await self.fetch(job)
            if not self.test_mode() and fresh is not None and self.eligible(fresh) and any(is_visual_attachment(a) for a in fresh.attachments) and signature(fresh) == before and not report_context(fresh.content) and self.config('scam_detector_dry_run', True) is False and self.private_review(fresh.guild) is not None:
                await asyncio.wait_for(fresh.delete(), REST_TIMEOUT)
                outcome = 'Removed by APBot'
                timeout_outcome = await self.timeout_sender(fresh)
        except nextcord.NotFound:
            outcome = 'Already removed (not attributed to APBot)'
        except (nextcord.HTTPException, asyncio.TimeoutError):
            outcome = 'Deletion failed or unconfirmed'
        finally:
            log.warning('Scam action: message=%s outcome=%s timeout=%s', job.message_id, outcome, timeout_outcome)
            embed.description = outcome
            embed.add_field(name='Messages Deleted', value='1' if outcome == 'Removed by APBot' else 'Unconfirmed' if outcome == 'Deletion failed or unconfirmed' else '0', inline=False)
            embed.add_field(name='Timeout', value=timeout_outcome, inline=False)
            try:
                await asyncio.wait_for(audit.edit(embed=embed), REST_TIMEOUT)
            except (nextcord.HTTPException, asyncio.TimeoutError):
                log.warning('Scam audit update failed: message=%s', job.message_id)


def setup(bot):
    bot.add_cog(ScamImageDetector(bot))
