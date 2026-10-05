"""Seam: goblin_cave is playable end-to-end within POC scope (no network)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.events import (
    ConditionAdded,
    LocationChanged,
    LongRestCompleted,
    SavingThrowResolved,
    SkillCheckResolved,
)
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "poc.db")
    await event_store.open()
    return event_store


def _scripted_tool(tool_name: str | None, args: dict | None, narration: str) -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if tool_name and calls["n"] == 1:
            return ModelResponse(
                parts=[ToolCallPart(tool_name=tool_name, args=args or {})]
            )
        return ModelResponse(parts=[TextPart(content=narration)])

    return FunctionModel(reply)


async def _play(
    store: EventStore,
    session_id: str,
    player_text: str,
    *,
    tool_name: str | None,
    args: dict | None,
    narration: str,
):
    return await TurnService(
        store,
        model=_scripted_tool(tool_name, args, narration),
    ).run_turn(session_id, player_text)


async def test_goblin_cave_playthrough_covers_poc_loop(store: EventStore) -> None:
    scenario = load_scenario("goblin_cave")
    assert scenario.intro
    assert len(scenario.locations) >= 2
    assert len(scenario.beats) >= 3

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=11)
    assert state.location == scenario.starting_location
    assert scenario.intro.splitlines()[0] in state.summary

    # Beat 1: scout Cave Mouth
    result = await _play(
        store,
        state.session_id,
        "I search the cave mouth for tracks.",
        tool_name="skill_check",
        args={"skill": "perception", "dc": 12, "reason": "scout tracks"},
        narration="Goblin tracks lead into the tunnel.",
    )
    assert result.status == "ok"
    assert any(isinstance(event, SkillCheckResolved) for event in result.events)

    # Beat 2a: enter Twisting Tunnel
    result = await _play(
        store,
        state.session_id,
        "I follow the tracks into the twisting tunnel.",
        tool_name="move_to",
        args={"location": "Twisting Tunnel", "reason": "follow tracks"},
        narration="The tunnel narrows; the air tastes wrong.",
    )
    assert any(isinstance(event, LocationChanged) for event in result.events)

    # Beat 2b: hazard Save, then Condition
    result = await _play(
        store,
        state.session_id,
        "I try to push through the foul air.",
        tool_name="saving_throw",
        args={"ability": "constitution", "dc": 13, "reason": "bad air"},
        narration="You gag but stay upright.",
    )
    assert any(isinstance(event, SavingThrowResolved) for event in result.events)

    result = await _play(
        store,
        state.session_id,
        "A war drum pounds from ahead.",
        tool_name="add_condition",
        args={"condition": "frightened", "reason": "war drum"},
        narration="The drum rattles your nerves.",
    )
    assert any(isinstance(event, ConditionAdded) for event in result.events)

    # Beat 3: reach Goblin Den, then rest outside
    result = await _play(
        store,
        state.session_id,
        "I press into the den and grab a crate, then withdraw.",
        tool_name="move_to",
        args={"location": "Goblin Den", "reason": "recover goods"},
        narration="You snatch a crate and slip back toward open air.",
    )
    assert any(isinstance(event, LocationChanged) for event in result.events)

    result = await _play(
        store,
        state.session_id,
        "I take a long rest outside the cave.",
        tool_name="long_rest",
        args={"reason": "camp outside"},
        narration="Dawn finds you steadier.",
    )
    assert any(isinstance(event, LongRestCompleted) for event in result.events)

    snapshot = await store.get_snapshot(state.session_id)
    events = await store.list_events(state.session_id)
    assert snapshot is not None
    assert snapshot.location == "Goblin Den"
    assert snapshot.character.conditions == []
    assert snapshot.character.hp == snapshot.character.max_hp
    assert len(events) >= 7
    assert any(event.type == "saving_throw_resolved" for event in events)
    turns = await store.list_recent_turns(state.session_id, limit=10)
    assert len(turns) == 6
    assert all(turn["status"] == "ok" for turn in turns)
