"""Seam: move_to Tool enforces authoritative exits."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.domain.events import LocationChanged
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "travel.db")
    await event_store.open()
    return event_store


def _move_then_narrate(location: str, narration: str) -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="move_to",
                        args={"location": location, "reason": "travel"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content=narration)])

    return FunctionModel(reply)


async def test_move_to_accepts_adjacent_exit(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(
        store,
        model=_move_then_narrate(
            "twisting_tunnel",
            "You slip into the twisting tunnel.",
        ),
    )

    result = await service.run_turn(state.session_id, "I enter the twisting tunnel.")

    assert result.status == "ok"
    assert any(isinstance(event, LocationChanged) for event in result.events)
    snapshot = await store.get_snapshot(state.session_id)
    assert snapshot is not None
    assert snapshot.location == "twisting_tunnel"
    assert "twisting_tunnel" in snapshot.world.visited_location_ids


async def test_move_to_rejects_unreachable_without_state_change(
    store: EventStore,
) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=2)
    before = await store.get_snapshot(state.session_id)
    service = TurnService(
        store,
        model=_move_then_narrate(
            "goblin_den",
            "The tunnel blocks a direct path to the den.",
        ),
    )

    result = await service.run_turn(state.session_id, "I try to go straight to the den.")
    after = await store.get_snapshot(state.session_id)

    assert result.status == "ok"
    assert not any(isinstance(event, LocationChanged) for event in result.events)
    assert before is not None and after is not None
    assert after.location == before.location == "cave_mouth"
