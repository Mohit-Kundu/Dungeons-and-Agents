"""Seam: Turn results expose reachable destinations to clients and the DM."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.services.stream_events import DoneEvent
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "guidance.db")
    await event_store.open()
    return event_store


def _narrate_only(text: str = "The cave waits.") -> FunctionModel:
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=text)])

    return FunctionModel(reply)


async def test_run_turn_includes_reachable_destinations(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=3)
    service = TurnService(store, model=_narrate_only())

    result = await service.run_turn(state.session_id, "I listen at the entrance.")

    assert [dest.id for dest in result.reachable] == ["twisting_tunnel"]
    assert result.reachable[0].name == "Twisting Tunnel"


async def test_stream_done_includes_reachable_destinations(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=4)
    service = TurnService(store, model=_narrate_only())

    events = [
        event async for event in service.stream_turn(state.session_id, "I listen at the entrance.")
    ]
    done = next(event for event in events if isinstance(event, DoneEvent))

    assert [dest.id for dest in done.reachable] == ["twisting_tunnel"]


async def test_dm_context_lists_reachable_destinations(store: EventStore) -> None:
    seen: dict[str, str] = {}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # Last user prompt carries Turn context.
        for message in reversed(messages):
            for part in message.parts:
                content = getattr(part, "content", None)
                if isinstance(content, str) and "Reachable destinations" in content:
                    seen["prompt"] = content
                    break
        return ModelResponse(parts=[TextPart(content="You hear dripping water.")])

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=5)
    service = TurnService(store, model=FunctionModel(reply))
    await service.run_turn(state.session_id, "I listen at the entrance.")

    assert "Reachable destinations" in seen["prompt"]
    assert "twisting_tunnel" in seen["prompt"]
    assert "Twisting Tunnel" in seen["prompt"]


async def test_branching_destinations_after_travel(store: EventStore) -> None:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="move_to",
                        args={"location": "twisting_tunnel", "reason": "enter"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="The tunnel forks ahead.")])

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=6)
    service = TurnService(store, model=FunctionModel(reply))
    result = await service.run_turn(state.session_id, "I enter the twisting tunnel.")

    assert {dest.id for dest in result.reachable} == {"cave_mouth", "goblin_den"}
