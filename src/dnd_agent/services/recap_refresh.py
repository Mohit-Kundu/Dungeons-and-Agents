"""Locked lazy Recap refresh after the persisted watermark (D-022)."""

from __future__ import annotations

from dataclasses import dataclass

from dnd_agent.agent.recap import RecapService
from dnd_agent.agent.providers import resolve_model
from dnd_agent.config import Settings, get_settings
from dnd_agent.domain.events import SummaryUpdated
from dnd_agent.domain.models import GameState
from dnd_agent.services.session_locks import SessionLockRegistry
from dnd_agent.store.event_store import EventStore


@dataclass(frozen=True)
class RecapRefreshResult:
    state: GameState
    refreshed: bool
    failed: bool = False


class RecapRefreshService:
    """Summarize successful Turns after GameState.recap_through_turn."""

    def __init__(
        self,
        store: EventStore,
        *,
        settings: Settings | None = None,
        recap: RecapService | None = None,
        locks: SessionLockRegistry | None = None,
    ) -> None:
        self._store = store
        self._settings = settings or get_settings()
        self._recap = recap if recap is not None else RecapService(resolve_model(self._settings))
        self._locks = locks if locks is not None else SessionLockRegistry()

    async def refresh(self, session_id: str) -> RecapRefreshResult:
        lock = await self._locks.lock_for(session_id)
        async with lock:
            return await self._refresh_locked(session_id)

    async def _refresh_locked(self, session_id: str) -> RecapRefreshResult:
        state = await self._store.get_snapshot(session_id)
        if state is None:
            raise KeyError(f"session not found: {session_id}")

        pending = await self._store.list_successful_turns_after(
            session_id,
            after_turn=state.recap_through_turn,
        )
        if not pending:
            return RecapRefreshResult(state=state, refreshed=False)

        try:
            summary = await self._recap.generate(
                prior_summary=state.summary,
                turns=pending,
            )
        except Exception:  # noqa: BLE001 - keep last good Recap
            fresh = await self._store.get_snapshot(session_id)
            assert fresh is not None
            return RecapRefreshResult(state=fresh, refreshed=False, failed=True)

        through_turn = max(int(turn["turn_number"]) for turn in pending)
        text = summary.strip()
        if not text or text == state.summary.strip():
            # Still advance watermark so a no-op model response does not loop forever.
            next_state = await self._store.append_event(
                session_id,
                SummaryUpdated(
                    summary=state.summary,
                    through_turn=through_turn,
                    reason="lazy_recap",
                ),
            )
            return RecapRefreshResult(state=next_state, refreshed=True)

        next_state = await self._store.append_event(
            session_id,
            SummaryUpdated(
                summary=text,
                through_turn=through_turn,
                reason="lazy_recap",
            ),
        )
        return RecapRefreshResult(state=next_state, refreshed=True)
