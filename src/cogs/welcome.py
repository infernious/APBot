"""Welcome introductions and a persistent sticky template, opt-in per guild."""
import asyncio
import io
import logging
import time
from collections import Counter
from datetime import datetime, timezone

import nextcord
from nextcord.ext import commands
from utils.welcome_validator import classify, Decision, TEMPLATE, resolve_channel_id, moderator_bypass, HARD_SPAM
from utils.welcome_store import WelcomeStore, StickyReminder
from utils.welcome_worker import Coalescer, Cooldown

log = logging.getLogger(__name__)
MARKER = 'AP Students • Welcome introduction template'
DELETE_GRACE_SECONDS = 0.5
NO_MENTIONS = nextcord.AllowedMentions.none()


TEMPLATE_BUTTON_ID = 'apbot:welcome:template:v1'
TEMPLATE_TITLE = 'Welcome to AP Students! 👋'
TEMPLATE_DESCRIPTION = (
    'Introduce yourself to the community! Feel free to use this template.\n\n'
    'You can write in your own words or skip anything you are uncomfortable sharing.\n'
    'Please keep this channel limited to introductions.'
)


def template_embed():
    return nextcord.Embed(title=TEMPLATE_TITLE, color=0x5865F2, description=TEMPLATE_DESCRIPTION)


def has_template_button(message):
    return any(
        getattr(component, 'custom_id', None) == TEMPLATE_BUTTON_ID
        for row in (getattr(message, 'components', ()) or ())
        for component in getattr(row, 'children', ())
    )


def is_own_reminder(bot, message):
    if bot.user is None or message.author.id != bot.user.id:
        return False
    embeds = getattr(message, 'embeds', ())
    # Keep recognizing old reminders so they can be migrated or cleaned up.
    if any(getattr(getattr(e, 'footer', None), 'text', None) == MARKER for e in embeds):
        return True
    return any(getattr(e, 'title', None) == TEMPLATE_TITLE and
               (has_template_button(message) or getattr(e, 'description', None) == TEMPLATE_DESCRIPTION)
               for e in embeds)


class TemplateView(nextcord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @nextcord.ui.button(label='Introduction Template', style=nextcord.ButtonStyle.secondary,
                        custom_id=TEMPLATE_BUTTON_ID)
    async def copy_template(self, button, interaction):
        if not self.cog.matches(interaction.guild, interaction.channel_id):
            return await interaction.response.send_message('This template is no longer active here.', ephemeral=True)
        await interaction.response.send_message('Copy this template and fill in anything you want to share:\n```\n'
                                                + TEMPLATE + '\n```', ephemeral=True, allowed_mentions=NO_MENTIONS)


class DiscordReminderTransport:
    def __init__(self, cog, channel):
        self.cog, self.channel = cog, channel
        self.verified = set()

    def is_reminder(self, message):
        return is_own_reminder(self.cog.bot, message)

    async def send(self):
        message = await self.channel.send(embed=template_embed(), view=self.cog.view, allowed_mentions=NO_MENTIONS)
        self.verified.add(message.id)
        return message.id

    async def exists(self, message_id):
        try:
            found = self.is_reminder(await self.channel.fetch_message(message_id))
            if found:
                self.verified.add(message_id)
            return found
        except nextcord.NotFound:
            return False

    async def delete(self, message_id):
        try:
            if message_id not in self.verified and not await self.exists(message_id):
                return True
            await self.channel.get_partial_message(message_id).delete()
            self.verified.discard(message_id)
            return True
        except nextcord.NotFound:
            self.verified.discard(message_id)
            return True
        except nextcord.HTTPException:
            log.warning('Welcome sticky cleanup failed: message=%s', message_id)
            return False

    async def snapshot(self):
        latest = None
        recovered = []
        async for message in self.channel.history(limit=50):
            if latest is None:
                latest = message.id
            if self.is_reminder(message):
                recovered.append(message.id)
                self.verified.add(message.id)
                # Migrate an existing legacy reminder at the bottom in place.
                if message.id == latest and (not has_template_button(message) or not any(
                    getattr(e, 'title', None) == TEMPLATE_TITLE and
                    getattr(e, 'description', None) == TEMPLATE_DESCRIPTION and
                    not getattr(getattr(e, 'footer', None), 'text', None)
                    for e in message.embeds
                )):
                    # Components may be absent from a transport snapshot. A known
                    # exact embed is still recognizable; failed repairs are retried.
                    if callable(getattr(message, 'edit', None)):
                        try:
                            await message.edit(embed=template_embed(), view=self.cog.view)
                        except nextcord.HTTPException:
                            log.warning('Welcome reminder migration failed: message=%s', message.id)
                            raise
        return latest, recovered


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = WelcomeStore(bot.db.base_db.database)
        self.view = TemplateView(self)
        self.bot.add_view(self.view)
        self.channel_id = None
        self.resolved = False
        self.reminder = None
        self.ready_once = False
        self.counters = Counter()
        self.dm_queue = asyncio.Queue(maxsize=50)
        self.log_queue = asyncio.Queue(maxsize=50)
        self.cooldown = Cooldown()
        self.delete_slots = asyncio.Semaphore(2)
        self.pending = set()
        self.edited = set()
        self.scheduler = Coalescer(self.refresh)
        self.tasks = []
        self._start_tasks()

    def _start_tasks(self):
        if self.tasks:
            return
        loop = asyncio.get_running_loop()
        self.tasks = [loop.create_task(self._initialize()), loop.create_task(self.scheduler.run()),
                      loop.create_task(self._dm_worker()), loop.create_task(self._log_worker())]

    def cog_unload(self):
        for task in self.tasks:
            task.cancel()
        self.view.stop()
        for queue in (self.dm_queue, self.log_queue):
            while not queue.empty():
                queue.get_nowait()
                queue.task_done()

    def settings(self):
        raw = self.bot.config.get('welcome', {})
        return raw if isinstance(raw, dict) else {}

    def configured_guild(self, guild):
        return guild is not None and str(guild.id) == str(self.bot.config.get('guild_id'))

    def resolve(self, guild):
        self.channel_id = resolve_channel_id(self.settings(), guild.text_channels)
        self.resolved = True
        if self.channel_id is None:
            log.error('Welcome channel missing, ambiguous or invalid: guild=%s', guild.id)
        return self.channel_id

    def matches(self, guild, channel_id):
        if self.settings().get('enabled') is not True or not self.configured_guild(guild):
            return False
        target = self.channel_id if self.resolved else self.resolve(guild)
        return target is not None and str(channel_id) == str(target)

    def bypass(self, member, channel):
        return moderator_bypass(self.settings(), member, channel)

    def check_permissions(self, channel):
        me = channel.guild.me
        if me is None:
            return
        perms = channel.permissions_for(me)
        for name in ('view_channel','send_messages','read_message_history','embed_links','manage_messages'):
            if not getattr(perms, name, False):
                log.error('Welcome missing permission: channel=%s permission=%s', channel.id, name)
        if not getattr(self.bot.intents, 'message_content', False):
            log.error('Welcome message_content intent disabled; deletion suspended')

    async def _initialize(self):
        await self.bot.wait_until_ready()
        self._ready()

    def _ready(self):
        self.ready_once = True
        if self.settings().get('enabled') is not True:
            return
        try:
            guild = self.bot.get_guild(int(self.bot.config.get('guild_id', 0)))
        except (TypeError, ValueError):
            return
        if guild is None:
            log.warning('Welcome configured guild unavailable')
            return
        target = self.resolve(guild)
        if target is not None:
            channel = guild.get_channel(target)
            if channel is not None:
                self.check_permissions(channel)
                self.schedule(ensure=True)
                log.warning('[Welcome] checking sticky in #%s (%s)', channel.name, target)
        if self.settings().get('log_enabled', True) is True and self.log_channel(guild) is None:
            log.warning('Welcome deletion log unavailable: configure a private #welcome-log channel (guild=%s)', guild.id)
        self.ready_once = True

    @commands.Cog.listener()
    async def on_ready(self):
        # Initial task covers cogs loaded after READY. Subsequent READYs reconcile.
        if self.ready_once:
            self._ready()

    def schedule(self, *, ensure=False):
        if self.settings().get('enabled') is True and self.settings().get('sticky_enabled', True) is True:
            self.scheduler.request(ensure=ensure)

    async def refresh(self, ensure):
        if self.settings().get('enabled') is not True or self.settings().get('sticky_enabled', True) is not True:
            return
        channel = self.bot.get_channel(self.channel_id) if self.channel_id else None
        if channel is None or not self.matches(channel.guild, channel.id):
            return
        if self.reminder is None or self.reminder.channel_id != channel.id:
            self.reminder = StickyReminder(self.store, DiscordReminderTransport(self, channel), channel.guild.id, channel.id)
            ensure = True
        try:
            current = await asyncio.wait_for(self.reminder.refresh(ensure=ensure), timeout=30)
        except (Exception, asyncio.CancelledError):
            self.reminder.needs_reconcile = True
            raise
        if ensure:
            log.warning('[Welcome] sticky reconciled: channel=%s message=%s', channel.id, current)
        if self.reminder.needs_reconcile:
            # Persistent cleanup failures need backoff, not immediate retries.
            raise RuntimeError('Welcome sticky cleanup incomplete')

    def channel_changed(self, guild):
        if self.configured_guild(guild):
            old = self.channel_id
            self.resolved = False
            new = self.resolve(guild)
            if new != old:
                self.schedule(ensure=True)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        self.channel_changed(channel.guild)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        self.channel_changed(channel.guild)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if before.name != after.name:
            self.channel_changed(after.guild)

    def deleted(self, channel_id, ids):
        if (self.settings().get('recover_deleted_sticky', True) is True and self.reminder
                and channel_id == self.reminder.channel_id and self.reminder.current in ids):
            self.schedule(ensure=True)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        self.deleted(payload.channel_id, {payload.message_id})

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        self.deleted(payload.channel_id, payload.message_ids)

    def log_channel(self, guild):
        """Resolve a same-guild text channel; never post to an @everyone-visible channel."""
        cfg = self.settings()
        if not self.configured_guild(guild) or cfg.get('log_enabled', True) is not True:
            return None
        lookup = {'channel_name': cfg.get('log_channel_name', 'welcome-log')}
        if 'log_channel_id' in cfg:
            lookup['channel_id'] = cfg['log_channel_id']
        target = resolve_channel_id(lookup, guild.text_channels)
        if target is None or target == self.channel_id:
            return None
        channel = guild.get_channel(target)
        everyone, me = getattr(guild, 'default_role', None), getattr(guild, 'me', None)
        if channel is None or everyone is None or me is None:
            return None
        if getattr(channel.permissions_for(everyone), 'view_channel', True):
            return None
        # Only staff permissions, not cosmetic role names, authorize reading logs.
        def staff(perms):
            return bool(getattr(perms, 'administrator', False) or getattr(perms, 'manage_messages', False))
        for role in getattr(guild, 'roles', ()):
            if role == everyone:
                continue
            effective = channel.permissions_for(role)
            if getattr(effective, 'view_channel', True) and not staff(getattr(role, 'permissions', effective)):
                return None
        for target, overwrite in getattr(channel, 'overwrites', {}).items():
            if getattr(overwrite, 'view_channel', None) is not True:
                continue
            if target == me:
                continue
            # Explicit view grants can combine with other roles. Unknown targets
            # or member-specific grants without staff privileges fail closed.
            if not staff(getattr(target, 'guild_permissions', getattr(target, 'permissions', None))):
                return None
        perms = channel.permissions_for(me)
        if not all(getattr(perms, name, False) for name in ('view_channel', 'send_messages', 'embed_links')):
            return None
        return channel

    def queue_log(self, message, reason):
        if self.settings().get('log_enabled', True) is not True:
            return
        if self.log_queue.full():
            self.counters['log_overload'] += 1
            log.warning('Welcome deletion log queue full: message=%s reason=%s', message.id, reason)
            return
        self.log_queue.put_nowait((message.guild.id, message.channel.id, message.author.id,
                                   message.id, reason, '' if reason == 'no_introduction_evidence' else (message.content or '')[:4000],
                                   len(getattr(message, 'attachments', []) or []), datetime.now(timezone.utc)))

    async def send_deletion_log(self, entry):
        gid, cid, uid, mid, reason, original, attachments, timestamp = entry
        channel = self.log_channel(self.bot.get_guild(gid))
        if channel is None:
            log.warning('Welcome deletion log unavailable: message=%s reason=%s', mid, reason)
            return
        # Discord embed descriptions support up to 4096 characters. Do not copy media.
        review = reason == 'no_introduction_evidence'
        # Render deleted text as inert code, not clickable links or injected markdown.
        safe = (original or 'No text content').replace('`', '`\u200b')[:4000]
        embed = nextcord.Embed(title='Welcome Message Flagged for Review' if review else 'Welcome Message Deleted',
                               color=0xFEE75C if review else 0xED4245,
                               description=f'[Review message](https://discord.com/channels/{gid}/{cid}/{mid})' if review else '```\n'+safe+'\n```', timestamp=timestamp)
        embed.add_field(name='Member', value=f'<@{uid}> (`{uid}`)', inline=False)
        embed.add_field(name='Channel', value=f'<#{cid}>', inline=True)
        embed.add_field(name='Reason', value=reason.replace('_', ' ').capitalize(), inline=True)
        embed.add_field(name='Message ID', value=str(mid), inline=False)
        if attachments:
            embed.add_field(name='Attachments', value=f'{attachments} (not copied)', inline=True)
        embed.set_footer(text='Not removed • Staff review' if review else 'Automatically removed by APBot • Welcome moderation')
        await asyncio.wait_for(channel.send(embed=embed, allowed_mentions=NO_MENTIONS), 15)

    async def _log_worker(self):
        while True:
            entry = await self.log_queue.get()
            try:
                await self.send_deletion_log(entry)
            except Exception:
                log.warning('Welcome deletion log failed: message=%s reason=%s', entry[3], entry[4])
            finally:
                self.log_queue.task_done()
            await asyncio.sleep(1)

    def queue_dm(self, message, reason):
        # Scam/raid notifications are deliberately suppressed. Ordinary mistakes get a copy.
        if reason in HARD_SPAM or self.dm_queue.full() or not self.cooldown.admit(message.author.id):
            return
        self.dm_queue.put_nowait((message.author, message.content or '', message.id))

    async def _dm_worker(self):
        while True:
            author, original, mid = await self.dm_queue.get()
            try:
                embed = nextcord.Embed(title='Your welcome message was removed', color=0xED4245,
                    description='Your message in #welcome was removed because it did not appear to be a valid introduction.\n\n'
                    'Please include at least one detail about yourself, such as a nickname, AP class, or interest. The template is optional; only share what you are comfortable sharing.\n\n'
                    'A copy of your original message is attached so you can revise and repost it when slowmode allows.\n\n'
                    'Here is a template you can use:\n```\n' + TEMPLATE + '\n```\n\n'
                    '**Think this was a mistake?**\n'
                    'Simply reply to this DM to contact our moderation team through Modmail. A staff member can review your concerns.')
                file = nextcord.File(io.BytesIO(original.encode('utf-8')), filename='original-introduction.txt')
                try:
                    await asyncio.wait_for(author.send(embed=embed, file=file, allowed_mentions=NO_MENTIONS), 15)
                finally:
                    file.close()
            except nextcord.Forbidden:
                if author.id in self.cooldown.entries:
                    self.cooldown.entries[author.id] = time.monotonic() + 3600
                log.warning('Welcome deletion DM unavailable: message=%s', mid)
            except Exception:
                log.warning('Welcome deletion DM failed: message=%s', mid)
            finally:
                self.dm_queue.task_done()
            await asyncio.sleep(3)  # Global maximum about 20 DMs/minute.

    def exempt(self, message, member=None):
        return (message.author.bot or getattr(message, 'webhook_id', None)
                or message.type not in (nextcord.MessageType.default, nextcord.MessageType.reply)
                or self.bypass(member or message.author, message.channel))

    def verdict(self, message):
        # Empty content can be a poll, forward, or other non-text message.
        media = any(getattr(message, attr, None) for attr in ('attachments','stickers','poll','message_snapshots'))
        if not message.content:
            return None  # Fail open if content isn't available.
        return classify(message.content, has_attachments=media, mass_ping=bool(getattr(message, 'mention_everyone', False)))

    async def remove(self, message, reason):
        try:
            await asyncio.wait_for(message.delete(), 15)
        except nextcord.NotFound:
            return True
        except (nextcord.HTTPException, asyncio.TimeoutError):
            log.warning('Welcome deletion failed: message=%s', message.id)
            return False
        log.info('Welcome removed: message=%s reason=%s', message.id, reason)
        self.queue_log(message, reason)
        self.queue_dm(message, reason)
        return True

    async def resolve_member(self, message):
        if isinstance(message.author, nextcord.Member):
            return message.author
        guild = message.guild
        uid = getattr(message.author, 'id', None)
        if uid is None:
            return None
        member = guild.get_member(uid)
        if member is None:
            try:
                member = await asyncio.wait_for(guild.fetch_member(uid), 15)
            except (nextcord.HTTPException, asyncio.TimeoutError):
                return None
        return member if isinstance(member, nextcord.Member) else None

    def flag_uncertain(self, message, verdict):
        if verdict is None or verdict.reason != 'no_introduction_evidence':
            return
        self.counters[verdict.reason] += 1
        log.warning('Welcome review: message=%s reason=%s', message.id, verdict.reason)
        if self.settings().get('dry_run', True) is False and getattr(self.bot.intents, 'message_content', False):
            self.queue_log(message, verdict.reason)

    async def validate(self, message, *, verdict=None, member=None):
        if self.exempt(message, member):
            return False
        verdict = verdict if verdict is not None else self.verdict(message)
        if verdict is None or verdict.decision != Decision.REJECT:
            return False
        self.counters[verdict.reason] += 1
        if self.settings().get('dry_run', True) is not False or not getattr(self.bot.intents, 'message_content', False):
            log.warning('Welcome dry-run would remove: message=%s reason=%s', message.id, verdict.reason)
            return False
        # Re-fetch after a brief correction window and inside the bounded slot.
        # Discord has no atomic compare-and-delete API; edits after DELETE is
        # sent cannot be guaranteed safe. Never delete on a failed fetch.
        await asyncio.sleep(DELETE_GRACE_SECONDS)
        edited = self.edited
        edited.discard(message.id)
        try:
            latest = await asyncio.wait_for(message.channel.fetch_message(message.id), 15)
        except (nextcord.HTTPException, asyncio.TimeoutError):
            return False
        if (not self.matches(latest.guild, latest.channel.id) or self.settings().get('dry_run', True) is not False
                or not getattr(self.bot.intents, 'message_content', False)):
            return False
        member = await self.resolve_member(latest)
        if member is None or self.exempt(latest, member):
            return False
        current = self.verdict(latest)
        if current is None or current.decision != Decision.REJECT:
            self.flag_uncertain(latest, current)
            return False
        if message.id in edited:
            # Another edit arrived during the fetch/member check. Fail open.
            self.counters['edit_during_fetch'] += 1
            return False
        return await self.remove(latest, current.reason)

    def reserve(self, mid):
        if mid in self.pending:
            return False
        if len(self.pending) >= 20:
            self.counters['overload'] += 1
            if self.counters['overload'] % 100 == 1:
                log.warning('Welcome pending capacity reached: message=%s', mid)
            return False
        self.pending.add(mid)
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        # Private interaction responses are not public channel traffic and
        # must never trigger a sticky refresh or introduction validation.
        if getattr(getattr(message, 'flags', None), 'ephemeral', False):
            return
        if not self.matches(message.guild, message.channel.id):
            return
        if is_own_reminder(self.bot, message):
            return
        # All retained messages (including staff/bots) affect the reminder position.
        if self.exempt(message):
            self.schedule()
            return
        verdict = self.verdict(message)
        if verdict is None or verdict.decision != Decision.REJECT:
            self.flag_uncertain(message, verdict)
            self.schedule()
            return
        if not self.reserve(message.id):
            self.schedule()
            return
        try:
            async with self.delete_slots:
                if not await self.validate(message, verdict=verdict):
                    self.schedule()
        finally:
            self.pending.discard(message.id)
            self.edited.discard(message.id)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        if 'content' not in payload.data or payload.guild_id is None:
            return
        if str(payload.guild_id) != str(self.bot.config.get('guild_id')):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not self.matches(guild, payload.channel_id):
            return
        if payload.message_id in self.pending:
            self.edited.add(payload.message_id)
            return
        if not self.reserve(payload.message_id):
            return
        try:
            async with self.delete_slots:
                channel = guild.get_channel(payload.channel_id)
                if channel is None:
                    return
                try:
                    message = await asyncio.wait_for(channel.fetch_message(payload.message_id), 15)
                except (nextcord.HTTPException, asyncio.TimeoutError):
                    return
                if getattr(message.author, 'bot', False) or getattr(message, 'webhook_id', None):
                    return
                member = await self.resolve_member(message)
                if member is None or self.exempt(message, member):
                    return
                verdict = self.verdict(message)
                self.flag_uncertain(message, verdict)
                await self.validate(message, verdict=verdict, member=member)
        finally:
            self.pending.discard(payload.message_id)
            self.edited.discard(payload.message_id)


def setup(bot):
    bot.add_cog(Welcome(bot))
