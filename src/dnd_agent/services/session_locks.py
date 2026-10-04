"""Shared per-Session locks so concurrent Turns serialize across requests."""

from __future__ import annotations

import asyncio


class SessionLockRegistry:
    """Process-local registry of asyncio locks keyed by session id."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def lock_for(self, session_id: str) -> asyncio.Lock:
        async with self._guard:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[session_id] = lock
            return lock
