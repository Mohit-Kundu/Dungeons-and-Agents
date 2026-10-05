"""Seam: TurnService + EventStore + RecapRefreshService deliver a guarded Goblin Cave."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.agent.recap import RecapService
from dnd_agent.domain.events import (
    EnemyGroupDamaged,
    ItemConsumed,
    ItemTaken,
    LocationChanged,
    ObjectiveCompleted,
    QuestCompleted,
)
from dnd_agent.services.recap_refresh import RecapRefreshService
from dnd_agent.services.session_locks import SessionLockRegistry
from dnd_agent.services.turns import TurnResult, TurnService
from dnd_agent.store.event_store import EventStore
from dnd_agent.world.intent import IntentProposer, ProposedActionIntent
from dnd_agent.world.travel import reachable_destinations


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "guarded.db")
    await event_store.open()
    return event_store


class StubIntent:
    def __init__(self, proposed: ProposedActionIntent) -> None:
        self.proposed = proposed

    async def propose(self, player_text: str, state: object) -> ProposedActionIntent:
        return self.proposed


class _AlwaysGeneral:
    async def propose(self, player_text: str, state: object) -> ProposedActionIntent:
        return ProposedActionIntent(kind="general", confidence="high")


def _capture_prompt(messages: list[ModelMessage], seen: dict[str, str]) -> None:
    for message in messages:
        for part in message.parts:
            content = getattr(part, "content", None)
            if isinstance(content, str) and "Incomplete objectives" in content:
                seen["prompt"] = content
                return


def _tools_then_narrate(
    calls: list[tuple[str, dict]],
    narration: str,
    *,
    seen_prompt: dict[str, str] | None = None,
) -> FunctionModel:
    counter = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if seen_prompt is not None:
            _capture_prompt(messages, seen_prompt)
        counter["n"] += 1
        index = counter["n"] - 1
        if index < len(calls):
            tool_name, args = calls[index]
            return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])
        return ModelResponse(parts=[TextPart(content=narration)])

    return FunctionModel(reply)


def _recap_model(text: str) -> FunctionModel:
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=text)])

    return FunctionModel(reply)


def _objective_ids(result: TurnResult) -> list[str]:
    return [obj.id for obj in result.incomplete_objectives]


def _reachable_ids(result: TurnResult) -> list[str]:
    return [dest.id for dest in result.reachable]


def _goblin_status(result: TurnResult):
    return next(enemy for enemy in result.enemies if enemy.id == "den_goblins")


def _assert_guidance_matches_state(result: TurnResult) -> None:
    assert _reachable_ids(result) == [
        dest.id for dest in reachable_destinations(result.state)
    ]
    assert {obj.id for obj in result.incomplete_objectives} == {
        obj.id for obj in result.state.world.objectives if obj.status != "completed"
    }
    goblins = next(g for g in result.state.world.enemy_groups if g.id == "den_goblins")
    status = _goblin_status(result)
    assert status.current_hp == goblins.current_hp
    assert status.max_hp == goblins.max_hp
    assert status.remaining_count == goblins.remaining_count
    assert status.defeated_count == goblins.defeated_count


def _assert_dm_prompt_has_guidance(prompt: str, result: TurnResult) -> None:
    assert "Incomplete objectives" in prompt
    assert "Reachable destinations" in prompt
    assert "Enemy groups" in prompt
    for dest_id in _reachable_ids(result):
        assert dest_id in prompt
    for obj_id in _objective_ids(result):
        assert obj_id in prompt
    for enemy in result.enemies:
        assert enemy.id in prompt


async def _play(
    store: EventStore,
    session_id: str,
    player_text: str,
    *,
    calls: list[tuple[str, dict]],
    narration: str,
    intent: IntentProposer | None = None,
    seen_prompt: dict[str, str] | None = None,
) -> TurnResult:
    return await TurnService(
        store,
        model=_tools_then_narrate(calls, narration, seen_prompt=seen_prompt),
        intent=intent if intent is not None else _AlwaysGeneral(),
    ).run_turn(session_id, player_text)


async def test_goblin_cave_guarded_playthrough(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=42)
    sid = state.session_id
    seen_prompt: dict[str, str] = {}

    # Reject unavailable stolen goods before the DM runs.
    rejected = await TurnService(
        store,
        model=_tools_then_narrate([], "DM must not run"),
        intent=StubIntent(
            ProposedActionIntent(
                kind="use",
                item_ids=["stolen_goods"],
                confidence="high",
            )
        ),
    ).run_turn(sid, "I grab the stolen goods from here.")
    assert rejected.status == "no_progress"
    assert rejected.events == []
    assert _objective_ids(rejected) == [
        "reach_goblin_den",
        "defeat_den_goblins",
        "recover_stolen_goods",
    ]
    assert _reachable_ids(rejected) == ["twisting_tunnel"]
    goblins = _goblin_status(rejected)
    assert goblins.current_hp == goblins.max_hp == 21
    assert goblins.remaining_count == 3
    _assert_guidance_matches_state(rejected)

    # Valid exit into the tunnel.
    tunnel = await _play(
        store,
        sid,
        "I follow the tracks into the twisting tunnel.",
        calls=[
            ("move_to", {"location": "twisting_tunnel", "reason": "follow tracks"}),
        ],
        narration="The tunnel narrows around you.",
        intent=StubIntent(
            ProposedActionIntent(
                kind="travel",
                destination_id="twisting_tunnel",
                confidence="high",
            )
        ),
        seen_prompt=seen_prompt,
    )
    assert tunnel.status == "ok"
    assert any(isinstance(event, LocationChanged) for event in tunnel.events)
    assert tunnel.state.location == "twisting_tunnel"
    assert set(_reachable_ids(tunnel)) == {"cave_mouth", "goblin_den"}
    assert "reach_goblin_den" in _objective_ids(tunnel)
    _assert_guidance_matches_state(tunnel)
    # Prompt lists pre-move guidance (still at cave mouth when the DM runs).
    assert "twisting_tunnel" in seen_prompt["prompt"]
    assert "reach_goblin_den" in seen_prompt["prompt"]

    # Use an available consumable from inventory.
    ration = await _play(
        store,
        sid,
        "I eat a ration.",
        calls=[("use_item", {"item_id": "ration", "reason": "eat before the den"})],
        narration="You finish a ration and steady yourself.",
        intent=StubIntent(
            ProposedActionIntent(kind="use", item_ids=["ration"], confidence="high")
        ),
        seen_prompt=seen_prompt,
    )
    assert ration.status == "ok"
    assert any(isinstance(event, ItemConsumed) for event in ration.events)
    rations = next(
        item for item in ration.state.character.inventory if item.id == "ration"
    )
    assert rations.qty == 4
    _assert_guidance_matches_state(ration)
    _assert_dm_prompt_has_guidance(seen_prompt["prompt"], ration)

    # Enter the den — completes the location Objective.
    den = await _play(
        store,
        sid,
        "I press into the goblin den.",
        calls=[("move_to", {"location": "goblin_den", "reason": "push in"})],
        narration="Smoke and war-drums fill the chamber.",
        intent=StubIntent(
            ProposedActionIntent(
                kind="travel",
                destination_id="goblin_den",
                confidence="high",
            )
        ),
        seen_prompt=seen_prompt,
    )
    assert den.status == "ok"
    assert any(
        isinstance(event, ObjectiveCompleted) and event.objective_id == "reach_goblin_den"
        for event in den.events
    )
    assert "reach_goblin_den" not in _objective_ids(den)
    assert _reachable_ids(den) == ["twisting_tunnel"]
    _assert_guidance_matches_state(den)
    assert "goblin_den" in seen_prompt["prompt"]

    # Acquire the portable stolen goods (general intent; DM must take_item).
    loot = await _play(
        store,
        sid,
        "I take the stolen village goods.",
        calls=[
            ("take_item", {"item_id": "stolen_goods", "reason": "recover loot"}),
        ],
        narration="You hoist the crates onto your back.",
        seen_prompt=seen_prompt,
    )
    assert loot.status == "ok"
    assert any(isinstance(event, ItemTaken) for event in loot.events)
    assert any(item.id == "stolen_goods" for item in loot.state.character.inventory)
    assert "recover_stolen_goods" not in _objective_ids(loot)
    assert _objective_ids(loot) == ["defeat_den_goblins"]
    _assert_guidance_matches_state(loot)
    _assert_dm_prompt_has_guidance(seen_prompt["prompt"], loot)

    # Defeat the only Enemy Group with three Check-funded resolutions.
    combat_calls: list[tuple[str, dict]] = []
    for _ in range(3):
        combat_calls.append(
            ("skill_check", {"skill": "athletics", "dc": 5, "reason": "strike goblin"})
        )
        combat_calls.append(
            (
                "resolve_enemy",
                {"enemy_group_id": "den_goblins", "reason": "blow lands"},
            )
        )

    fight = await _play(
        store,
        sid,
        "I fight the goblin raiders.",
        calls=combat_calls,
        narration="The last goblin falls silent.",
        intent=StubIntent(
            ProposedActionIntent(
                kind="resolve_enemy",
                enemy_group_ids=["den_goblins"],
                confidence="high",
            )
        ),
        seen_prompt=seen_prompt,
    )

    assert fight.status == "ok"
    damages = [e for e in fight.events if isinstance(e, EnemyGroupDamaged)]
    assert len(damages) == 3
    assert damages[-1].current_hp == 0
    defeated = _goblin_status(fight)
    assert defeated.current_hp == 0
    assert defeated.remaining_count == 0
    assert defeated.defeated_count == 3
    assert any(
        isinstance(e, ObjectiveCompleted) and e.objective_id == "defeat_den_goblins"
        for e in fight.events
    )
    assert any(isinstance(e, QuestCompleted) for e in fight.events)
    assert fight.incomplete_objectives == []
    assert fight.state.quest.status == "completed"
    assert all(obj.status == "completed" for obj in fight.state.world.objectives)
    _assert_guidance_matches_state(fight)
    assert "den_goblins" in seen_prompt["prompt"]
    assert "twisting_tunnel" in seen_prompt["prompt"]


async def test_mid_play_restore_preserves_authoritative_state(tmp_path: Path) -> None:
    db_path = tmp_path / "restore.db"
    store = EventStore(db_path)
    await store.open()

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=77)
    sid = state.session_id

    await _play(
        store,
        sid,
        "I enter the twisting tunnel.",
        calls=[
            ("move_to", {"location": "twisting_tunnel", "reason": "advance"}),
        ],
        narration="Damp stone closes in.",
        intent=StubIntent(
            ProposedActionIntent(
                kind="travel",
                destination_id="twisting_tunnel",
                confidence="high",
            )
        ),
    )
    await _play(
        store,
        sid,
        "I enter the den.",
        calls=[("move_to", {"location": "goblin_den", "reason": "advance"})],
        narration="You breach the den.",
        intent=StubIntent(
            ProposedActionIntent(
                kind="travel",
                destination_id="goblin_den",
                confidence="high",
            )
        ),
    )
    await _play(
        store,
        sid,
        "I take the stolen goods.",
        calls=[
            ("take_item", {"item_id": "stolen_goods", "reason": "recover"}),
        ],
        narration="Crates secured.",
        intent=StubIntent(
            ProposedActionIntent(
                kind="use",
                item_ids=["stolen_goods"],
                confidence="high",
            )
        ),
    )
    mid = await _play(
        store,
        sid,
        "I strike a goblin.",
        calls=[
            ("skill_check", {"skill": "athletics", "dc": 5, "reason": "strike"}),
            (
                "resolve_enemy",
                {"enemy_group_id": "den_goblins", "reason": "hit"},
            ),
        ],
        narration="One raider drops.",
        intent=StubIntent(
            ProposedActionIntent(
                kind="resolve_enemy",
                enemy_group_ids=["den_goblins"],
                confidence="high",
            )
        ),
    )
    assert mid.state.location == "goblin_den"
    goblins = next(g for g in mid.state.world.enemy_groups if g.id == "den_goblins")
    assert goblins.current_hp == 14
    assert goblins.remaining_count == 2

    recap = await RecapRefreshService(
        store, recap=RecapService(_recap_model("Brynn reached the den and struck once."))
    ).refresh(sid)
    assert recap.refreshed is True
    assert recap.state.recap_through_turn >= 1

    before = await store.get_snapshot(sid)
    assert before is not None
    before_den = next(loc for loc in before.world.locations if loc.id == "goblin_den")
    fingerprint = {
        "inventory": [item.model_dump() for item in before.character.inventory],
        "location": before.location,
        "surroundings": {
            "items": [item.model_dump() for item in before_den.items],
            "interactables": [item.model_dump() for item in before_den.interactables],
        },
        "locations": [loc.model_dump() for loc in before.world.locations],
        "enemies": [g.model_dump() for g in before.world.enemy_groups],
        "objectives": [o.model_dump() for o in before.world.objectives],
        "quest": before.quest.model_dump(),
        "reachable": [d.id for d in reachable_destinations(before)],
        "summary": before.summary,
        "recap_through_turn": before.recap_through_turn,
    }

    restored_store = EventStore(db_path)
    await restored_store.open()
    after = await restored_store.get_snapshot(sid)
    assert after is not None
    after_den = next(loc for loc in after.world.locations if loc.id == "goblin_den")
    assert [item.model_dump() for item in after.character.inventory] == fingerprint[
        "inventory"
    ]
    assert after.location == fingerprint["location"]
    assert [item.model_dump() for item in after_den.items] == fingerprint["surroundings"][
        "items"
    ]
    assert [item.model_dump() for item in after_den.interactables] == fingerprint[
        "surroundings"
    ]["interactables"]
    assert [loc.model_dump() for loc in after.world.locations] == fingerprint["locations"]
    assert [g.model_dump() for g in after.world.enemy_groups] == fingerprint["enemies"]
    assert [o.model_dump() for o in after.world.objectives] == fingerprint["objectives"]
    assert after.quest.model_dump() == fingerprint["quest"]
    assert [d.id for d in reachable_destinations(after)] == fingerprint["reachable"]
    assert after.summary == fingerprint["summary"]
    assert after.recap_through_turn == fingerprint["recap_through_turn"]


async def test_concurrent_turn_and_recap_do_not_corrupt_state(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=88)
    sid = state.session_id
    locks = SessionLockRegistry()

    await store.add_turn(
        sid,
        player_text="I scout the mouth.",
        narration="Tracks lead inward.",
        status="ok",
    )

    active = 0
    max_active = 0

    async def slow_reply(
        messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        return ModelResponse(parts=[TextPart(content="You hold at the cave mouth.")])

    async def slow_recap(
        messages: list[ModelMessage], info: AgentInfo
    ) -> ModelResponse:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        return ModelResponse(parts=[TextPart(content="Brynn scouted the cave mouth.")])

    turn_service = TurnService(
        store,
        model=FunctionModel(slow_reply),
        intent=_AlwaysGeneral(),
        locks=locks,
    )
    recap_service = RecapRefreshService(
        store,
        recap=RecapService(FunctionModel(slow_recap)),
        locks=locks,
    )

    turn_result, recap_result = await asyncio.gather(
        turn_service.run_turn(sid, "I wait and listen."),
        recap_service.refresh(sid),
    )

    assert max_active == 1
    assert turn_result.status == "ok"
    snapshot = await store.get_snapshot(sid)
    assert snapshot is not None
    assert snapshot.location == "cave_mouth"
    assert snapshot.world.is_seeded()
    turns = await store.list_recent_turns(sid, limit=10)
    assert len(turns) == 2
    assert all(turn["status"] == "ok" for turn in turns)
    # Order decides watermark: Recap-first folds turn 1; Turn-first then Recap folds both.
    assert snapshot.recap_through_turn in {1, 2}
    if recap_result.refreshed:
        assert snapshot.summary == "Brynn scouted the cave mouth."
        assert snapshot.recap_through_turn >= 1
    rebuilt = await store.rebuild_snapshot(sid)
    assert rebuilt == snapshot
