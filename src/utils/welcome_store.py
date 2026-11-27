"""Mongo-backed reminder state; no database handler modifications."""
import asyncio

SAVE_TIMEOUT = 5


class WelcomeStore:
    def __init__(self, database):
        self.collection = database['welcome_reminders']

    @staticmethod
    def key(guild_id, channel_id):
        return f'{guild_id}:{channel_id}'

    async def read(self, guild_id, channel_id):
        doc = await self.collection.find_one({'_id': self.key(guild_id, channel_id)})
        return doc or {'current': None, 'stale': []}

    async def save(self, guild_id, channel_id, current, stale):
        await self.collection.update_one(
            {'_id': self.key(guild_id, channel_id)},
            {'$set': {'current': current, 'stale': sorted(set(stale) - {current})}},
            upsert=True,
        )


class StickyReminder:
    """Memory-first, single-worker state; persist IDs before deleting old reminders.

    Stored IDs are untrusted until transport verifies ownership. A failed save does not prevent verified cleanup; retry persistence later.
    """
    def __init__(self, store, transport, guild_id, channel_id):
        self.store, self.transport = store, transport
        self.guild_id, self.channel_id = guild_id, channel_id
        self.current = None
        self.stale = set()
        self.loaded = False
        self.needs_reconcile = True
        self.unsaved = False

    async def refresh(self, *, ensure=False, recovered=None):
        if not self.loaded:
            state = await self.store.read(self.guild_id, self.channel_id)
            self.current = state.get('current')
            self.stale = set(state.get('stale', []))
            self.loaded = True
        ensure = ensure or self.needs_reconcile
        if ensure:
            if recovered is None and hasattr(self.transport, 'snapshot'):
                latest, recovered = await self.transport.snapshot()
            else:
                latest = await self.transport.latest_id()
                recovered = recovered or ()
            self.stale.update(recovered)
        else:
            latest = None
            recovered = ()
        old = self.current
        reuse = ensure and latest is not None and (latest in recovered or (latest == old and await self.transport.exists(old)))
        # If cleanup is blocked, do not keep creating more reminders.
        if len(self.stale - {old}) >= 50 and not reuse:
            for mid in sorted(self.stale - {old}):
                if await self.transport.delete(mid):
                    self.stale.discard(mid)
            if len(self.stale - {old}) >= 50:
                self.needs_reconcile = True
                raise RuntimeError('Welcome cleanup blocked; check channel permissions')
        if reuse:
            self.current = latest
        else:
            self.current = await self.transport.send()
        if old and old != self.current:
            self.stale.add(old)
        self.stale.discard(self.current)
        # One durable write per move; stale IDs already deleted are harmless on restart.
        save_error = None
        if self.current != old or self.stale or self.unsaved:
            self.unsaved = True
            try:
                await asyncio.wait_for(self.store.save(self.guild_id, self.channel_id, self.current, self.stale), SAVE_TIMEOUT)
            except Exception as exc:
                save_error = exc
            else:
                self.unsaved = False
        for mid in sorted(self.stale):
            if await self.transport.delete(mid):
                self.stale.discard(mid)
        self.needs_reconcile = bool(self.stale) or self.unsaved
        if save_error is not None:
            raise save_error
        return self.current
