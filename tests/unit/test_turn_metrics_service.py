"""Seam: TurnService persists turn_metrics after completed Turns."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "svc.db")
    await event_store.open()
    return event_store


async def test_run_turn_persists_metrics_for_ok_turn(store: EventStore) -> None:
    async def reply(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[TextPart(content="The torch flickers.")],
            model_name="test-dm",
        )

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(store, model=FunctionModel(reply))
    result = await service.run_turn(state.session_id, "I look around.")

    assert result.status == "ok"
    metrics = await store.list_turn_metrics(state.session_id)
    assert len(metrics) == 1
    assert metrics[0].turn_number == result.turn_number
    assert metrics[0].status == "ok"
    assert len(metrics[0].model_requests) >= 1
    assert metrics[0].model_requests[0].role == "dm"


async def test_no_progress_turn_persists_metrics(store: EventStore) -> None:
    async def boom(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise AssertionError("DM must not run for no_progress")

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(store, model=FunctionModel(boom))
    result = await service.run_turn(state.session_id, "I go to the Goblin Den.")

    assert result.status == "no_progress"
    metrics = await store.list_turn_metrics(state.session_id)
    assert len(metrics) == 1
    assert metrics[0].status == "no_progress"
    assert metrics[0].tool_calls == 0
