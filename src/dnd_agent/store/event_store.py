"""SQLite Event store with Snapshot cache."""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from dnd_agent.content.loader import load_character, load_scenario
from dnd_agent.domain.events import EVENT_ADAPTER, Event, SessionCreated
from dnd_agent.domain.models import GameState
from dnd_agent.store.reducer import apply_event, fold_events
from dnd_agent.telemetry.aggregate import TurnTelemetry

SeedFactory = Callable[[], int]
IdFactory = Callable[[], str]


def _default_seed() -> int:
    return secrets.randbelow(2**31)


def _default_session_id() -> str:
    return f"sess_{secrets.token_hex(4)}"


class EventStore:
    """Append-only Event log with cached Snapshots."""

    def __init__(
        self,
        db_path: Path | str,
        *,
        seed_factory: SeedFactory | None = None,
        id_factory: IdFactory | None = None,
    ) -> None:
        self._db_path = Path(db_path)
        self._ready = False
        self._seed_factory: SeedFactory = seed_factory or _default_seed
        self._id_factory: IdFactory = id_factory or _default_session_id

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
                CREATE TABLE IF NOT EXISTS turn_metrics (
                    session_id TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    tool_calls INTEGER NOT NULL,
                    tool_errors INTEGER NOT NULL,
                    cost_usd REAL,
                    unknown_pricing_count INTEGER NOT NULL,
                    models_json TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn_number),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
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
        sid = session_id if session_id is not None else self._id_factory()
        seed = rng_seed if rng_seed is not None else self._seed_factory()

        world = scenario.build_world(current_location_id=scenario.starting_location)
        event = SessionCreated(
            session_id=sid,
            scenario_id=scenario.id,
            character=character,
            location=scenario.starting_location,
            quest=scenario.quest,
            rng_seed=seed,
            summary=scenario.briefing(),
            world=world,
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

    def _ensure_playable_world(self, state: GameState) -> GameState:
        """Lazily seed PlayableWorld for Sessions created before authoritative content."""
        if state.world.is_seeded():
            return state
        scenario = load_scenario(state.scenario_id)
        location_id = scenario.resolve_location_id(state.location) or scenario.starting_location
        world = scenario.build_world(current_location_id=location_id)
        return state.model_copy(update={"location": location_id, "world": world})

    async def _persist_snapshot(self, state: GameState) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO snapshots (session_id, state_json)
                VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET state_json = excluded.state_json
                """,
                (state.session_id, state.model_dump_json()),
            )
            await db.commit()

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
        state = GameState.model_validate_json(row[0])
        upgraded = self._ensure_playable_world(state)
        if upgraded != state:
            await self._persist_snapshot(upgraded)
        return upgraded

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
        state = self._ensure_playable_world(fold_events(events))
        await self._persist_snapshot(state)
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

    async def list_successful_turns_after(
        self,
        session_id: str,
        *,
        after_turn: int,
    ) -> list[dict[str, Any]]:
        """Return successful Turns with turn_number greater than after_turn, ascending."""
        await self._ensure_open()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT turn_number, player_text, narration, status
                FROM turns
                WHERE session_id = ?
                  AND turn_number > ?
                  AND status = 'ok'
                ORDER BY turn_number ASC
                """,
                (session_id, after_turn),
            )
            rows = await cursor.fetchall()
        return [
            {
                "turn_number": turn_number,
                "player_text": player_text,
                "narration": narration,
                "status": status,
            }
            for turn_number, player_text, narration, status in rows
        ]

    async def get_latest_turn(self, session_id: str) -> dict[str, Any] | None:
        turns = await self.list_recent_turns(session_id, limit=1)
        return turns[-1] if turns else None

    async def add_turn_metrics(
        self,
        session_id: str,
        turn_number: int,
        telemetry: TurnTelemetry,
    ) -> None:
        await self._ensure_open()
        if telemetry.session_id != session_id or telemetry.turn_number != turn_number:
            raise ValueError("telemetry session_id/turn_number must match arguments")
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO turn_metrics (
                    session_id, turn_number, status, latency_ms,
                    input_tokens, output_tokens, tool_calls, tool_errors,
                    cost_usd, unknown_pricing_count, models_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, turn_number) DO UPDATE SET
                    status = excluded.status,
                    latency_ms = excluded.latency_ms,
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens,
                    tool_calls = excluded.tool_calls,
                    tool_errors = excluded.tool_errors,
                    cost_usd = excluded.cost_usd,
                    unknown_pricing_count = excluded.unknown_pricing_count,
                    models_json = excluded.models_json
                """,
                (
                    session_id,
                    turn_number,
                    telemetry.status,
                    telemetry.latency_ms,
                    telemetry.input_tokens,
                    telemetry.output_tokens,
                    telemetry.tool_calls,
                    telemetry.tool_errors,
                    telemetry.cost_usd,
                    telemetry.unknown_pricing_count,
                    telemetry.model_dump_json(include={"model_requests"}),
                ),
            )
            await db.commit()

    async def list_turn_metrics(self, session_id: str) -> list[TurnTelemetry]:
        await self._ensure_open()
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT turn_number, status, latency_ms, input_tokens, output_tokens,
                       tool_calls, tool_errors, cost_usd, unknown_pricing_count, models_json
                FROM turn_metrics
                WHERE session_id = ?
                ORDER BY turn_number ASC
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()

        result: list[TurnTelemetry] = []
        for (
            turn_number,
            status,
            latency_ms,
            input_tokens,
            output_tokens,
            tool_calls,
            tool_errors,
            cost_usd,
            unknown_pricing_count,
            models_json,
        ) in rows:
            payload = json.loads(models_json)
            model_requests = (
                payload.get("model_requests", payload)
                if isinstance(payload, dict)
                else payload
            )
            result.append(
                TurnTelemetry(
                    session_id=session_id,
                    turn_number=int(turn_number),
                    status=status,  # type: ignore[arg-type]
                    latency_ms=float(latency_ms),
                    input_tokens=int(input_tokens),
                    output_tokens=int(output_tokens),
                    tool_calls=int(tool_calls),
                    tool_errors=int(tool_errors),
                    cost_usd=cost_usd,
                    unknown_pricing_count=int(unknown_pricing_count),
                    model_requests=model_requests,
                )
            )
        return result
