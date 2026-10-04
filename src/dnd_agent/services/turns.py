"""Turn orchestration: load context, run DM Agent, persist narration."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.models import Model
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.usage import UsageLimits

from dnd_agent.agent.deps import TurnDeps
from dnd_agent.agent.dm_agent import build_dm_agent
from dnd_agent.config import Settings, get_settings
from dnd_agent.domain.events import Event
from dnd_agent.domain.models import GameState
from dnd_agent.services.session_locks import SessionLockRegistry
from dnd_agent.services.stream_events import (
    ROLL_EVENT_TYPES,
    STATE_EVENT_TYPES,
    DoneEvent,
    ErrorEvent,
    NarrationDelta,
    RollEvent,
    StateChangedEvent,
    ToolCallEvent,
    TurnStreamEvent,
)
from dnd_agent.store.event_store import EventStore


@dataclass(frozen=True)
class TurnResult:
    session_id: str
    turn_number: int
    player_text: str
    narration: str
    state: GameState
    events: list[Event]
    status: str


def _format_context(state: GameState, recent_turns: list[dict]) -> str:
    history_lines: list[str] = []
    for turn in recent_turns:
        history_lines.append(f"Player: {turn['player_text']}")
        history_lines.append(f"DM: {turn['narration']}")
    history = "\n".join(history_lines) if history_lines else "(no prior turns)"
    return (
        f"Current GameState JSON:\n{state.model_dump_json(indent=2)}\n\n"
        f"Recent turns:\n{history}\n\n"
        f"Rolling summary:\n{state.summary or '(empty)'}"
    )


def _tool_args(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    return {"value": raw}


def _domain_stream_events(event: Event) -> list[TurnStreamEvent]:
    payload = event.model_dump(mode="json")
    emitted: list[TurnStreamEvent] = []
    if event.type in ROLL_EVENT_TYPES:
        emitted.append(RollEvent(event=payload))
    if event.type in STATE_EVENT_TYPES:
        emitted.append(StateChangedEvent(event=payload))
    return emitted


class TurnService:
    def __init__(
        self,
        store: EventStore,
        *,
        settings: Settings | None = None,
        model: Model | str | None = None,
        locks: SessionLockRegistry | None = None,
    ) -> None:
        self._store = store
        self._settings = settings or get_settings()
        self._model = model if model is not None else self._settings.model
        self._agent = build_dm_agent(self._model)
        self._locks = locks if locks is not None else SessionLockRegistry()

    async def stream_turn(
        self, session_id: str, player_text: str
    ) -> AsyncIterator[TurnStreamEvent]:
        text = player_text.strip()
        if not text:
            raise ValueError("player_text must not be empty")

        lock = await self._locks.lock_for(session_id)
        async with lock:
            async for event in self._stream_turn_locked(session_id, text):
                yield event

    async def _stream_turn_locked(
        self, session_id: str, text: str
    ) -> AsyncIterator[TurnStreamEvent]:
        state = await self._store.get_snapshot(session_id)
        if state is None:
            raise KeyError(f"session not found: {session_id}")

        recent = await self._store.list_recent_turns(
            session_id,
            limit=self._settings.memory_recent_turns,
        )
        deps = TurnDeps(store=self._store, session_id=session_id)
        prompt = (
            f"{_format_context(state, recent)}\n\n"
            f"Player action:\n{text}\n\n"
            "Resolve the action. Call tools for any Check or roll before narrating the outcome."
        )

        status = "ok"
        narration_parts: list[str] = []
        emitted_domain = 0

        try:
            async with self._agent.run_stream_events(
                prompt,
                deps=deps,
                usage_limits=UsageLimits(
                    request_limit=self._settings.max_tool_calls_per_turn + 2,
                    tool_calls_limit=self._settings.max_tool_calls_per_turn,
                ),
            ) as run:
                async for agent_event in run:
                    if isinstance(agent_event, FunctionToolCallEvent):
                        yield ToolCallEvent(
                            tool_name=agent_event.part.tool_name,
                            args=_tool_args(agent_event.part.args),
                        )
                    elif isinstance(agent_event, FunctionToolResultEvent):
                        new_events = deps.events_this_turn[emitted_domain:]
                        emitted_domain = len(deps.events_this_turn)
                        for domain_event in new_events:
                            for stream_event in _domain_stream_events(domain_event):
                                yield stream_event
                    elif isinstance(agent_event, PartStartEvent) and isinstance(
                        agent_event.part, TextPart
                    ):
                        if agent_event.part.content:
                            narration_parts.append(agent_event.part.content)
                            yield NarrationDelta(text=agent_event.part.content)
                    elif isinstance(agent_event, PartDeltaEvent) and isinstance(
                        agent_event.delta, TextPartDelta
                    ):
                        if agent_event.delta.content_delta:
                            narration_parts.append(agent_event.delta.content_delta)
                            yield NarrationDelta(text=agent_event.delta.content_delta)
                    elif isinstance(agent_event, AgentRunResultEvent):
                        output = str(agent_event.result.output).strip()
                        if output and not narration_parts:
                            narration_parts.append(output)
                            yield NarrationDelta(text=output)
        except Exception as exc:  # noqa: BLE001 - persist aborted Turn
            status = "aborted"
            message = f"The Turn could not be completed: {exc}"
            narration_parts = [message]
            yield ErrorEvent(message=message)

        # Flush any domain Events not tied to a tool-result callback
        new_events = deps.events_this_turn[emitted_domain:]
        for domain_event in new_events:
            for stream_event in _domain_stream_events(domain_event):
                yield stream_event

        narration = "".join(narration_parts).strip() or "The world holds its breath."
        turn_number = await self._store.add_turn(
            session_id,
            player_text=text,
            narration=narration,
            status=status,
        )
        fresh_state = await self._store.get_snapshot(session_id)
        assert fresh_state is not None
        yield DoneEvent(
            turn_number=turn_number,
            status=status,
            state=fresh_state,
            narration=narration,
        )

    async def run_turn(self, session_id: str, player_text: str) -> TurnResult:
        text = player_text.strip()
        if not text:
            raise ValueError("player_text must not be empty")

        state = await self._store.get_snapshot(session_id)
        if state is None:
            raise KeyError(f"session not found: {session_id}")

        recent = await self._store.list_recent_turns(
            session_id,
            limit=self._settings.memory_recent_turns,
        )
        deps = TurnDeps(store=self._store, session_id=session_id)
        prompt = (
            f"{_format_context(state, recent)}\n\n"
            f"Player action:\n{text}\n\n"
            "Resolve the action. Call tools for any Check or roll before narrating the outcome."
        )

        status = "ok"
        try:
            result = await self._agent.run(
                prompt,
                deps=deps,
                usage_limits=UsageLimits(
                    request_limit=self._settings.max_tool_calls_per_turn + 2,
                    tool_calls_limit=self._settings.max_tool_calls_per_turn,
                ),
            )
            narration = result.output.strip() or "The world holds its breath."
        except Exception as exc:  # noqa: BLE001 - persist aborted Turn
            status = "aborted"
            narration = f"The Turn could not be completed: {exc}"

        turn_number = await self._store.add_turn(
            session_id,
            player_text=text,
            narration=narration,
            status=status,
        )
        fresh_state = await self._store.get_snapshot(session_id)
        assert fresh_state is not None
        return TurnResult(
            session_id=session_id,
            turn_number=turn_number,
            player_text=text,
            narration=narration,
            state=fresh_state,
            events=list(deps.events_this_turn),
            status=status,
        )
