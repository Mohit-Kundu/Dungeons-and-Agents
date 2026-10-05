"""Seam: invalid explicit travel is a no-progress Turn without DM resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.domain.events import LocationChanged
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore
from dnd_agent.world.travel import detect_travel_destination


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "reject.db")
    await event_store.open()
    return event_store


def test_detect_travel_destination_requires_travel_verb() -> None:
    from dnd_agent.content.loader import load_scenario
    from dnd_agent.domain.models import (
        AbilityScores,
        Character,
        GameState,
        Quest,
    )

    scenario = load_scenario("goblin_cave")
    state = GameState(
        session_id="s",
        scenario_id="goblin_cave",
        character=Character(
            id="c",
            name="Brynn",
            level=1,
            class_name="Fighter",
            abilities=AbilityScores(
                strength=16,
                dexterity=12,
                constitution=14,
                intelligence=10,
                wisdom=11,
                charisma=13,
            ),
            proficiency_bonus=2,
            max_hp=12,
            hp=12,
            hit_die=10,
            hit_dice_total=1,
            hit_dice_remaining=1,
            armor_class=16,
        ),
        location="cave_mouth",
        quest=Quest(
            id="q",
            title="Q",
            summary="Q",
            status="active",
        ),
        rng_seed=1,
        world=scenario.build_world(current_location_id="cave_mouth"),
    )

    assert detect_travel_destination("I search the cave mouth for tracks.", state) is None
    assert detect_travel_destination("I go to the Goblin Den.", state) == "goblin_den"
    assert detect_travel_destination("I enter the twisting tunnel.", state) == "twisting_tunnel"


async def test_rejected_travel_is_no_progress_turn_without_dm(store: EventStore) -> None:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        return ModelResponse(parts=[TextPart(content="DM should not run.")])

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=8)
    service = TurnService(store, model=FunctionModel(reply))

    result = await service.run_turn(state.session_id, "I go to the Goblin Den.")

    assert calls["n"] == 0
    assert result.status == "no_progress"
    assert result.events == []
    assert "no route" in result.narration.lower()
    assert [dest.id for dest in result.reachable] == ["twisting_tunnel"]
    turns = await store.list_recent_turns(state.session_id, limit=1)
    assert turns[0]["status"] == "no_progress"
    assert not any(
        isinstance(event, LocationChanged) for event in await store.list_events(state.session_id)
    )


async def test_rejected_travel_stream_emits_done_without_awaiting_dm(
    store: EventStore,
) -> None:
    async def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise AssertionError("DM agent must not run for rejected travel")

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=9)
    service = TurnService(store, model=FunctionModel(boom))

    events = [
        event
        async for event in service.stream_turn(state.session_id, "I travel to the Goblin Den.")
    ]
    done = events[-1]
    assert done.type == "done"
    assert done.status == "no_progress"
    assert "no route" in done.narration.lower()
    assert [dest.id for dest in done.reachable] == ["twisting_tunnel"]
