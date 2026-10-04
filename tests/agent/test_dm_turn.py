"""Seam: DM Agent calls skill_check via FunctionModel (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.domain.events import SkillCheckResolved
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "turn.db")
    await event_store.open()
    return event_store


def _skill_check_then_narrate():
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
                            "reason": "search the cave mouth",
                        },
                    )
                ]
            )
        return ModelResponse(
            parts=[TextPart(content="You spot goblin tracks leading deeper into the cave.")]
        )

    return FunctionModel(reply)


async def test_turn_runs_skill_check_tool_and_persists_event(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=42)
    service = TurnService(store, model=_skill_check_then_narrate())

    result = await service.run_turn(state.session_id, "I search the cave mouth carefully.")

    assert result.status == "ok"
    assert "goblin tracks" in result.narration.lower()
    assert any(isinstance(event, SkillCheckResolved) for event in result.events)
    check = next(event for event in result.events if isinstance(event, SkillCheckResolved))
    assert check.skill == "perception"
    assert check.dc == 12

    events = await store.list_events(state.session_id)
    assert any(isinstance(event, SkillCheckResolved) for event in events)
    snapshot = await store.get_snapshot(state.session_id)
    assert snapshot is not None
    assert snapshot.rng_seed != 42  # seed advanced after the Check


async def test_refused_unknown_skill_does_not_break_state(store: EventStore) -> None:
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        has_tool_return = any(
            getattr(part, "part_kind", None) == "tool-return"
            for message in messages
            for part in message.parts
        )
        if not has_tool_return:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="skill_check",
                        args={"skill": "not_a_real_skill", "dc": 10, "reason": "test"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="Nothing conclusive happens.")])

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=7)
    before = await store.get_snapshot(state.session_id)
    service = TurnService(store, model=FunctionModel(reply))

    result = await service.run_turn(state.session_id, "I try something impossible.")
    after = await store.get_snapshot(state.session_id)

    assert result.status == "ok"
    assert before is not None and after is not None
    assert after.rng_seed == before.rng_seed
    assert not any(isinstance(event, SkillCheckResolved) for event in result.events)
