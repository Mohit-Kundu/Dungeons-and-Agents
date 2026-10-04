"""SQLite Event store with Snapshot cache."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
from dnd_agent.content.loader import load_character, load_scenario
from dnd_agent.domain.events import EVENT_ADAPTER, Event, SessionCreated
from dnd_agent.domain.models import GameState
from dnd_agent.store.reducer import apply_event, fold_events


class EventStore:
    """Append-only Event log with cached Snapshots."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._ready = False

    async def open(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    player_text TEXT NOT NULL,
                    narration TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id),
                    UNIQUE(session_id, turn_number)
                );
                """
            )
            await db.commit()
        self._ready = True

    async def _ensure_open(self) -> None:
        if not self._ready:
            await self.open()

    async def create_session(
        self,
        *,
        scenario_id: str = "goblin_cave",
        character_id: str | None = None,
        rng_seed: int | None = None,
        session_id: str | None = None,
    ) -> GameState:
        await self._ensure_open()
        scenario = load_scenario(scenario_id)
        resolved_character_id = character_id or scenario.character_id
        character = load_character(resolved_character_id)
        sid = session_id or f"sess_{secrets.token_hex(4)}"
        seed = rng_seed if rng_seed is not None else secrets.randbelow(2**31)

        event = SessionCreated(
            session_id=sid,
            scenario_id=scenario.id,
            character=character,
            location=scenario.starting_location,
            quest=scenario.quest,
            rng_seed=seed,
        )
        state = apply_event(None, event)
        now = datetime.now(UTC).isoformat()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO sessions (id, scenario_id, created_at) VALUES (?, ?, ?)",
                (sid, scenario.id, now),
            )
            await db.execute(
                """
                INSERT INTO events (session_id, type, payload_json, ts)
                VALUES (?, ?, ?, ?)
                """,
                (sid, event.type, event.model_dump_json(), now),
            )
            await db.execute(
                """
                INSERT INTO snapshots (session_id, state_json)
                VALUES (?, ?)
                """,
                (sid, state.model_dump_json()),
            )
            await db.commit()

        return state

    async def append_event(self, session_id: str, event: Event) -> GameState:
        await self._ensure_open()
        current = await self.get_snapshot(session_id)
        if current is None:
            raise KeyError(f"session not found: {session_id}")

        next_state = apply_event(current, event)
        now = datetime.now(UTC).isoformat()

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO events (session_id, type, payload_json, ts)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, event.type, event.model_dump_json(), now),
            )
            await db.execute(
                """
                UPDATE snapshots SET state_json = ? WHERE session_id = ?
                """,
                (next_state.model_dump_json(), session_id),
            )
            await db.commit()

        return next_state

    async def get_snapshot(self, session_id: str) -> GameState | None:
        await self._ensure_open()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "SELECT state_json FROM snapshots WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return GameState.model_validate_json(row[0])

    async def list_events(self, session_id: str) -> list[Event]:
        await self._ensure_open()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT payload_json FROM events
                WHERE session_id = ?
                ORDER BY seq ASC
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()

        events: list[Event] = []
        for (payload,) in rows:
            data: dict[str, Any] = json.loads(payload)
            events.append(EVENT_ADAPTER.validate_python(data))
        return events

    async def rebuild_snapshot(self, session_id: str) -> GameState:
        """Rebuild Snapshot from the Event log (source of truth)."""
        events = await self.list_events(session_id)
        state = fold_events(events)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO snapshots (session_id, state_json)
                VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET state_json = excluded.state_json
                """,
                (session_id, state.model_dump_json()),
            )
            await db.commit()
        return state

    async def add_turn(
        self,
        session_id: str,
        *,
        player_text: str,
        narration: str,
        status: str = "ok",
    ) -> int:
        await self._ensure_open()
        if await self.get_snapshot(session_id) is None:
            raise KeyError(f"session not found: {session_id}")
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT COALESCE(MAX(turn_number), 0) + 1
                FROM turns WHERE session_id = ?
                """,
                (session_id,),
            )
            row = await cursor.fetchone()
            turn_number = int(row[0]) if row else 1
            await db.execute(
                """
                INSERT INTO turns (
                    session_id, turn_number, player_text, narration, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, turn_number, player_text, narration, status, now),
            )
            await db.commit()
        return turn_number

    async def list_recent_turns(self, session_id: str, *, limit: int) -> list[dict[str, Any]]:
        await self._ensure_open()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT turn_number, player_text, narration, status
                FROM turns
                WHERE session_id = ?
                ORDER BY turn_number DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = await cursor.fetchall()
        turns = [
            {
                "turn_number": turn_number,
                "player_text": player_text,
                "narration": narration,
                "status": status,
            }
            for turn_number, player_text, narration, status in rows
        ]
        turns.reverse()
        return turns
