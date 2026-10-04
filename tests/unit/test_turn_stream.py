"""Seam: TurnService streams narration / tool / roll events with a session lock."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from dnd_agent.domain.events import SkillCheckResolved
from dnd_agent.services.session_locks import SessionLockRegistry
from dnd_agent.services.stream_events import (
    DoneEvent,
    ErrorEvent,
    NarrationDelta,
    RollEvent,
    ToolCallEvent,
)
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "stream.db")
    await event_store.open()
    return event_store


def _streaming_skill_check_model() -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="skill_check",
                        args={
                            "skill": "perception",
                            "dc": 12,
                            "reason": "search",
                        },
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="You spot goblin tracks.")])

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        calls["n"] += 1
        if calls["n"] == 1:
            yield {0: DeltaToolCall(name="skill_check")}
            yield {
                0: DeltaToolCall(
                    json_args='{"skill":"perception","dc":12,"reason":"search"}'
                )
            }
        else:
            text = "You spot goblin tracks."
            for index in range(0, len(text), 8):
                yield text[index : index + 8]

    return FunctionModel(reply, stream_function=stream)


async def test_stream_turn_emits_tool_roll_narration_and_done(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=42)
    service = TurnService(store, model=_streaming_skill_check_model())

    events = [event async for event in service.stream_turn(state.session_id, "I search.")]

    assert any(isinstance(event, ToolCallEvent) for event in events)
    assert any(isinstance(event, RollEvent) for event in events)
    deltas = [event.text for event in events if isinstance(event, NarrationDelta)]
    assert "".join(deltas) == "You spot goblin tracks."
    done = next(event for event in events if isinstance(event, DoneEvent))
    assert done.status == "ok"
    assert done.turn_number == 1
    assert done.state.session_id == state.session_id


async def test_session_lock_serializes_concurrent_turns(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    active = 0
    max_active = 0

    async def slow_stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str]:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        yield "A quiet moment passes."
        active -= 1

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content="unused")])

    locks = SessionLockRegistry()
    # Two service instances (like two HTTP requests) must still serialize.
    service_a = TurnService(
        store, model=FunctionModel(reply, stream_function=slow_stream), locks=locks
    )
    service_b = TurnService(
        store, model=FunctionModel(reply, stream_function=slow_stream), locks=locks
    )

    async def play(service: TurnService, label: str) -> list[object]:
        return [event async for event in service.stream_turn(state.session_id, label)]

    await asyncio.gather(play(service_a, "first"), play(service_b, "second"))
    assert max_active == 1
    turns = await store.list_recent_turns(state.session_id, limit=10)
    assert [turn["turn_number"] for turn in turns] == [1, 2]


def _abort_after_check_model() -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="skill_check",
                        args={"skill": "perception", "dc": 10, "reason": "look"},
                    )
                ]
            )
        raise RuntimeError("model blew up")

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        calls["n"] += 1
        if calls["n"] == 1:
            yield {0: DeltaToolCall(name="skill_check")}
            yield {0: DeltaToolCall(json_args='{"skill":"perception","dc":10,"reason":"look"}')}
        else:
            raise RuntimeError("model blew up")

    return FunctionModel(reply, stream_function=stream)


async def test_aborted_stream_keeps_committed_roll(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=9)
    before_seed = state.rng_seed
    service = TurnService(store, model=_abort_after_check_model())

    events = [
        event async for event in service.stream_turn(state.session_id, "I look around.")
    ]

    assert any(isinstance(event, RollEvent) for event in events)
    assert any(isinstance(event, ErrorEvent) for event in events)
    done = next(event for event in events if isinstance(event, DoneEvent))
    assert done.status == "aborted"

    persisted = await store.list_events(state.session_id)
    assert any(isinstance(event, SkillCheckResolved) for event in persisted)
    snapshot = await store.get_snapshot(state.session_id)
    assert snapshot is not None
    assert snapshot.rng_seed != before_seed
    turns = await store.list_recent_turns(state.session_id, limit=1)
    assert turns[0]["status"] == "aborted"
