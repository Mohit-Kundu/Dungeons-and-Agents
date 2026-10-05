"""Seam: Turn results expose incomplete objectives, enemies, and destinations."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.domain.events import (
    EnemyGroupDamaged,
    ItemTaken,
    LocationChanged,
    ObjectiveCompleted,
    QuestCompleted,
)
from dnd_agent.services.stream_events import DoneEvent
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore
from dnd_agent.store.reducer import fold_events
from dnd_agent.world.intent import ProposedActionIntent


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "objectives_turn.db")
    await event_store.open()
    return event_store


def _narrate_only(text: str = "The cave waits.") -> FunctionModel:
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=text)])

    return FunctionModel(reply)


class _AlwaysGeneral:
    async def propose(self, player_text: str, state: object) -> ProposedActionIntent:
        return ProposedActionIntent(kind="general", confidence="high")


async def test_turn_lists_incomplete_objectives_and_enemies(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=30)
    service = TurnService(store, model=_narrate_only(), intent=_AlwaysGeneral())

    result = await service.run_turn(state.session_id, "I look around.")

    assert [obj.id for obj in result.incomplete_objectives] == [
        "reach_goblin_den",
        "defeat_den_goblins",
        "recover_stolen_goods",
    ]
    assert [dest.id for dest in result.reachable] == ["twisting_tunnel"]
    assert result.enemies
    goblins = next(enemy for enemy in result.enemies if enemy.id == "den_goblins")
    assert goblins.current_hp == goblins.max_hp == 21
    assert goblins.remaining_count == 3


async def test_reaching_den_completes_location_objective_once(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=31)
    await store.append_event(
        state.session_id,
        LocationChanged(location="twisting_tunnel", reason="setup"),
    )

    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="move_to",
                        args={"location": "goblin_den", "reason": "push in"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="You enter the den.")])

    service = TurnService(store, model=FunctionModel(reply), intent=_AlwaysGeneral())
    result = await service.run_turn(state.session_id, "I enter the goblin den.")

    completed = [e for e in result.events if isinstance(e, ObjectiveCompleted)]
    assert [e.objective_id for e in completed] == ["reach_goblin_den"]
    assert "reach_goblin_den" not in {o.id for o in result.incomplete_objectives}
    assert result.state.quest.status == "active"

    # Repeated evaluation emits nothing new.
    again = await service.run_turn(state.session_id, "I catch my breath.")
    assert not any(isinstance(e, ObjectiveCompleted) for e in again.events)


async def test_all_predicates_complete_quest_and_replay(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=32)
    sid = state.session_id
    await store.append_event(sid, LocationChanged(location="twisting_tunnel", reason="setup"))
    await store.append_event(sid, LocationChanged(location="goblin_den", reason="setup"))
    await store.append_event(
        sid,
        ItemTaken(
            item_id="stolen_goods",
            name="Stolen Village Goods",
            qty=1,
            from_location_id="goblin_den",
            reason="setup",
        ),
    )
    await store.append_event(
        sid,
        EnemyGroupDamaged(
            enemy_group_id="den_goblins",
            damage=21,
            current_hp=0,
            reason="setup",
        ),
    )

    service = TurnService(store, model=_narrate_only("The den falls silent."), intent=_AlwaysGeneral())
    result = await service.run_turn(sid, "I survey the chamber.")

    assert any(isinstance(e, ObjectiveCompleted) for e in result.events)
    assert any(isinstance(e, QuestCompleted) for e in result.events)
    assert result.incomplete_objectives == []
    assert result.state.quest.status == "completed"
    assert all(o.status == "completed" for o in result.state.world.objectives)

    events = await store.list_events(sid)
    rebuilt = await store.rebuild_snapshot(sid)
    assert rebuilt == fold_events(events)
    assert rebuilt.quest.status == "completed"

    later = await service.run_turn(sid, "I wait.")
    assert later.state.quest.status == "completed"
    assert not any(isinstance(e, QuestCompleted) for e in later.events)


async def test_take_item_completes_inventory_objective(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=35)
    sid = state.session_id
    await store.append_event(sid, LocationChanged(location="twisting_tunnel", reason="setup"))
    await store.append_event(sid, LocationChanged(location="goblin_den", reason="setup"))

    # Flush location objective created by setup travel.
    await TurnService(store, model=_narrate_only(), intent=_AlwaysGeneral()).run_turn(
        sid, "I arrive in the den."
    )

    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="take_item",
                        args={"item_id": "stolen_goods", "reason": "recover loot"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="You secure the crates.")])

    service = TurnService(store, model=FunctionModel(reply), intent=_AlwaysGeneral())
    result = await service.run_turn(sid, "I take the stolen goods.")

    assert any(
        isinstance(e, ObjectiveCompleted) and e.objective_id == "recover_stolen_goods"
        for e in result.events
    )
    assert "recover_stolen_goods" not in {o.id for o in result.incomplete_objectives}


async def test_stream_done_includes_guidance(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=33)
    service = TurnService(store, model=_narrate_only(), intent=_AlwaysGeneral())
    events = [event async for event in service.stream_turn(state.session_id, "I listen.")]
    done = next(event for event in events if isinstance(event, DoneEvent))
    assert [obj.id for obj in done.incomplete_objectives] == [
        "reach_goblin_den",
        "defeat_den_goblins",
        "recover_stolen_goods",
    ]
    assert done.enemies[0].id == "den_goblins"


async def test_dm_context_lists_objectives_and_enemies(store: EventStore) -> None:
    seen: dict[str, str] = {}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        for message in reversed(messages):
            for part in message.parts:
                content = getattr(part, "content", None)
                if isinstance(content, str) and "Incomplete objectives" in content:
                    seen["prompt"] = content
                    break
        return ModelResponse(parts=[TextPart(content="You hear dripping water.")])

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=34)
    service = TurnService(store, model=FunctionModel(reply), intent=_AlwaysGeneral())
    await service.run_turn(state.session_id, "I listen.")

    assert "Incomplete objectives" in seen["prompt"]
    assert "reach_goblin_den" in seen["prompt"]
    assert "Enemy groups" in seen["prompt"]
    assert "den_goblins" in seen["prompt"]
