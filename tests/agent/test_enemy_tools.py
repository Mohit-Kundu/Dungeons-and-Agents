"""Seam: resolve_enemy Tool mutates Enemy Groups through Events."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from dnd_agent.domain.events import EnemyGroupDamaged, LocationChanged, SkillCheckResolved
from dnd_agent.services.stream_events import DoneEvent, StateChangedEvent
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore
from dnd_agent.store.reducer import fold_events
from dnd_agent.world.intent import ProposedActionIntent, available_enemy_group_ids


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "enemy.db")
    await event_store.open()
    return event_store


async def _session_in_den(store: EventStore, *, rng_seed: int) -> str:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=rng_seed)
    await store.append_event(
        state.session_id,
        LocationChanged(location="twisting_tunnel", reason="setup"),
    )
    await store.append_event(
        state.session_id,
        LocationChanged(location="goblin_den", reason="setup"),
    )
    return state.session_id


def _tools_then_narrate(calls: list[tuple[str, dict]], narration: str) -> FunctionModel:
    state = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        state["n"] += 1
        index = state["n"] - 1
        if index < len(calls):
            tool_name, args = calls[index]
            return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])
        return ModelResponse(parts=[TextPart(content=narration)])

    return FunctionModel(reply)


class _AlwaysResolveGoblins:
    async def propose(self, player_text: str, state: object) -> ProposedActionIntent:
        return ProposedActionIntent(
            kind="resolve_enemy",
            enemy_group_ids=["den_goblins"],
            confidence="high",
        )


class _AlwaysGeneral:
    async def propose(self, player_text: str, state: object) -> ProposedActionIntent:
        return ProposedActionIntent(kind="general", confidence="high")


async def test_successful_check_then_resolve_applies_damage(store: EventStore) -> None:
    session_id = await _session_in_den(store, rng_seed=21)
    service = TurnService(
        store,
        model=_tools_then_narrate(
            [
                (
                    "skill_check",
                    {"skill": "athletics", "dc": 5, "reason": "strike goblin"},
                ),
                (
                    "resolve_enemy",
                    {"enemy_group_id": "den_goblins", "reason": "strike lands"},
                ),
            ],
            "One goblin crumples under the blow.",
        ),
        intent=_AlwaysResolveGoblins(),
    )

    result = await service.run_turn(session_id, "I attack the goblins.")

    assert result.status == "ok"
    assert any(isinstance(event, SkillCheckResolved) and event.success for event in result.events)
    damaged = next(event for event in result.events if isinstance(event, EnemyGroupDamaged))
    assert damaged.damage == 7
    assert damaged.current_hp == 14
    goblins = next(g for g in result.state.world.enemy_groups if g.id == "den_goblins")
    assert goblins.current_hp == 14
    assert goblins.max_hp == 21
    assert goblins.remaining_count == 2
    assert goblins.defeated_count == 1


async def test_failed_check_blocks_damage(store: EventStore) -> None:
    session_id = await _session_in_den(store, rng_seed=22)
    before = await store.get_snapshot(session_id)
    service = TurnService(
        store,
        model=_tools_then_narrate(
            [
                (
                    "skill_check",
                    {"skill": "athletics", "dc": 30, "reason": "wild swing"},
                ),
                (
                    "resolve_enemy",
                    {"enemy_group_id": "den_goblins", "reason": "try anyway"},
                ),
            ],
            "Your swing goes wide.",
        ),
        intent=_AlwaysResolveGoblins(),
    )

    result = await service.run_turn(session_id, "I swing wildly.")
    after = await store.get_snapshot(session_id)

    assert result.status == "ok"
    assert any(
        isinstance(event, SkillCheckResolved) and not event.success for event in result.events
    )
    assert not any(isinstance(event, EnemyGroupDamaged) for event in result.events)
    assert before is not None and after is not None
    before_hp = next(g.current_hp for g in before.world.enemy_groups if g.id == "den_goblins")
    after_hp = next(g.current_hp for g in after.world.enemy_groups if g.id == "den_goblins")
    assert after_hp == before_hp


async def test_repeated_resolutions_defeat_group_and_block_further_damage(
    store: EventStore,
) -> None:
    session_id = await _session_in_den(store, rng_seed=23)
    for hit in range(3):
        service = TurnService(
            store,
            model=_tools_then_narrate(
                [
                    (
                        "skill_check",
                        {"skill": "athletics", "dc": 5, "reason": f"hit {hit}"},
                    ),
                    (
                        "resolve_enemy",
                        {"enemy_group_id": "den_goblins", "reason": f"hit {hit}"},
                    ),
                ],
                f"Strike {hit + 1} lands.",
            ),
            intent=_AlwaysResolveGoblins(),
        )
        result = await service.run_turn(session_id, f"I attack again ({hit}).")
        assert result.status == "ok"
        assert any(isinstance(event, EnemyGroupDamaged) for event in result.events)

    snapshot = await store.get_snapshot(session_id)
    assert snapshot is not None
    goblins = next(g for g in snapshot.world.enemy_groups if g.id == "den_goblins")
    assert goblins.current_hp == 0
    assert goblins.remaining_count == 0
    assert goblins.defeated_count == 3
    assert "den_goblins" not in available_enemy_group_ids(snapshot)

    # Intent gate rejects defeated enemies; use general to reach the Tool error path.
    service = TurnService(
        store,
        model=_tools_then_narrate(
            [
                ("skill_check", {"skill": "athletics", "dc": 5, "reason": "overkill"}),
                (
                    "resolve_enemy",
                    {"enemy_group_id": "den_goblins", "reason": "overkill"},
                ),
            ],
            "There are no goblins left to hit.",
        ),
        intent=_AlwaysGeneral(),
    )
    result = await service.run_turn(session_id, "I strike the fallen.")
    assert not any(isinstance(event, EnemyGroupDamaged) for event in result.events)


async def test_resolve_enemy_rejects_remote_target(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=24)
    before = await store.get_snapshot(state.session_id)
    service = TurnService(
        store,
        model=_tools_then_narrate(
            [
                ("skill_check", {"skill": "athletics", "dc": 5, "reason": "remote"}),
                (
                    "resolve_enemy",
                    {"enemy_group_id": "den_goblins", "reason": "remote"},
                ),
            ],
            "The den is too far.",
        ),
        intent=_AlwaysGeneral(),
    )

    result = await service.run_turn(state.session_id, "I attack goblins from outside.")
    after = await store.get_snapshot(state.session_id)

    assert not any(isinstance(event, EnemyGroupDamaged) for event in result.events)
    assert before is not None and after is not None
    assert after.world.enemy_groups == before.world.enemy_groups


async def test_streaming_and_replay_expose_enemy_hp(store: EventStore) -> None:
    session_id = await _session_in_den(store, rng_seed=25)
    calls = {"n": 0}
    scripted = [
        ("skill_check", {"skill": "athletics", "dc": 5, "reason": "stream hit"}),
        ("resolve_enemy", {"enemy_group_id": "den_goblins", "reason": "stream hit"}),
    ]

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        index = calls["n"] - 1
        if index < len(scripted):
            tool_name, args = scripted[index]
            return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])
        return ModelResponse(parts=[TextPart(content="The raiders stagger.")])

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        calls["n"] += 1
        index = calls["n"] - 1
        if index < len(scripted):
            tool_name, args = scripted[index]
            yield {0: DeltaToolCall(name=tool_name)}
            yield {0: DeltaToolCall(json_args=json.dumps(args))}
        else:
            yield "The raiders stagger."

    service = TurnService(
        store,
        model=FunctionModel(reply, stream_function=stream),
        intent=_AlwaysResolveGoblins(),
    )

    stream_events = [
        event async for event in service.stream_turn(session_id, "I attack.")
    ]
    state_changed = [
        event
        for event in stream_events
        if isinstance(event, StateChangedEvent)
        and event.event.get("type") == "enemy_group_damaged"
    ]
    assert state_changed
    done = next(event for event in stream_events if isinstance(event, DoneEvent))
    goblins = next(g for g in done.state.world.enemy_groups if g.id == "den_goblins")
    dump = goblins.model_dump()
    assert dump["current_hp"] == 14
    assert dump["max_hp"] == 21
    assert dump["remaining_count"] == 2
    assert dump["defeated_count"] == 1

    events = await store.list_events(session_id)
    rebuilt = await store.rebuild_snapshot(session_id)
    assert rebuilt == fold_events(events)
    assert rebuilt == done.state
