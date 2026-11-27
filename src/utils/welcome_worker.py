"""Bounded, event-driven sticky scheduling and notification admission."""
import asyncio
import time


class Coalescer:
    def __init__(self, callback, *, quiet=3, maximum=10, retry=15):
        self.callback = callback
        self.quiet, self.maximum, self.retry = quiet, maximum, retry
        self.event = asyncio.Event()
        self.first = self.last = None
        self.ensure = False

    def request(self, *, ensure=False):
        now = time.monotonic()
        if self.first is None:
            self.first = now
        self.last = now
        self.ensure |= ensure
        self.event.set()

    async def run(self):
        while True:
            await self.event.wait()
            while not self.ensure:
                delay = min(self.last + self.quiet, self.first + self.maximum) - time.monotonic()
                if delay <= 0:
                    break
                self.event.clear()
                try:
                    await asyncio.wait_for(self.event.wait(), delay)
                except asyncio.TimeoutError:
                    pass
            ensure = self.ensure
            self.first = self.last = None
            self.ensure = False
            self.event.clear()
            try:
                await self.callback(ensure)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Never busy-loop on outage; requests during backoff coalesce.
                import logging
                logging.getLogger(__name__).exception('Welcome sticky refresh failed; retrying')
                await asyncio.sleep(self.retry)
                self.request(ensure=True)


class Cooldown:
    def __init__(self, capacity=4096, seconds=600):
        self.entries = {}
        self.capacity, self.seconds = capacity, seconds

    def admit(self, key, now=None):
        now = time.monotonic() if now is None else now
        if self.entries.get(key, -1) > now:
            return False
        if len(self.entries) >= self.capacity:
            self.entries = {k:v for k,v in self.entries.items() if v > now}
        if len(self.entries) >= self.capacity:
            return False
        self.entries[key] = now + self.seconds
        return True
