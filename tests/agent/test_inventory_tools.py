"""Seam: take_item / use_item Tools mutate inventory through Events."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.domain.events import ItemConsumed, ItemTaken, LocationChanged
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore
from dnd_agent.world.intent import ProposedActionIntent, available_item_ids


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "inventory.db")
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


def _tool_then_narrate(tool_name: str, args: dict, narration: str) -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[ToolCallPart(tool_name=tool_name, args=args)]
            )
        return ModelResponse(parts=[TextPart(content=narration)])

    return FunctionModel(reply)


async def test_take_item_moves_portable_nearby_stack(store: EventStore) -> None:
    session_id = await _session_in_den(store, rng_seed=11)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "take_item",
            {"item_id": "stolen_goods", "reason": "recover loot"},
            "You haul the stolen crates onto your back.",
        ),
        intent=_AlwaysGeneral(),
    )

    result = await service.run_turn(session_id, "I take the stolen goods.")

    assert result.status == "ok"
    assert any(isinstance(event, ItemTaken) for event in result.events)
    snapshot = await store.get_snapshot(session_id)
    assert snapshot is not None
    den = next(loc for loc in snapshot.world.locations if loc.id == "goblin_den")
    assert not any(item.id == "stolen_goods" for item in den.items)
    assert any(item.id == "stolen_goods" for item in snapshot.character.inventory)
    assert "stolen_goods" in available_item_ids(snapshot)


async def test_take_item_rejects_non_portable_without_mutation(store: EventStore) -> None:
    session_id = await _session_in_den(store, rng_seed=12)
    before = await store.get_snapshot(session_id)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "take_item",
            {"item_id": "war_drum", "reason": "try to pocket drum"},
            "The war drum is too heavy to pocket.",
        ),
        intent=_AlwaysGeneral(),
    )

    result = await service.run_turn(session_id, "I try to take the war drum.")
    after = await store.get_snapshot(session_id)

    assert result.status == "ok"
    assert not any(isinstance(event, ItemTaken) for event in result.events)
    assert before is not None and after is not None
    assert after.character.inventory == before.character.inventory


async def test_use_item_consumes_ration_and_removes_exhausted_stack(
    store: EventStore,
) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=13)
    # Drain rations to 1 via consume events so the next use removes the stack.
    for _ in range(4):
        await store.append_event(
            state.session_id,
            ItemConsumed(item_id="ration", qty=1, source="inventory", reason="setup"),
        )

    service = TurnService(
        store,
        model=_tool_then_narrate(
            "use_item",
            {"item_id": "ration", "reason": "eat last ration"},
            "You finish the last ration.",
        ),
        intent=_AlwaysUseRation(),
    )

    result = await service.run_turn(state.session_id, "I eat a ration.")

    assert result.status == "ok"
    assert any(isinstance(event, ItemConsumed) for event in result.events)
    snapshot = await store.get_snapshot(state.session_id)
    assert snapshot is not None
    assert not any(item.id == "ration" for item in snapshot.character.inventory)
    assert "ration" not in available_item_ids(snapshot)


async def test_use_item_rejects_remote_without_mutation(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=14)
    before = await store.get_snapshot(state.session_id)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "use_item",
            {"item_id": "stolen_goods", "reason": "from afar"},
            "Those crates are deeper in the cave.",
        ),
        intent=_AlwaysGeneral(),
    )

    result = await service.run_turn(state.session_id, "I try to use the stolen goods from here.")
    after = await store.get_snapshot(state.session_id)

    assert result.status == "ok"
    assert not any(
        isinstance(event, (ItemTaken, ItemConsumed)) for event in result.events
    )
    assert before is not None and after is not None
    assert after.character.inventory == before.character.inventory
    assert after.world.locations == before.world.locations
    assert after.location == before.location


async def test_stream_take_emits_state_changed_and_replay_matches(
    store: EventStore,
) -> None:
    from collections.abc import AsyncIterator

    from pydantic_ai.models.function import DeltaToolCall

    from dnd_agent.services.stream_events import DoneEvent, StateChangedEvent
    from dnd_agent.store.reducer import fold_events
    from dnd_agent.world.intent import validate_action_intent

    session_id = await _session_in_den(store, rng_seed=15)
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
        return ModelResponse(parts=[TextPart(content="You secure the stolen goods.")])

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        calls["n"] += 1
        if calls["n"] == 1:
            yield {0: DeltaToolCall(name="take_item")}
            yield {
                0: DeltaToolCall(
                    json_args='{"item_id":"stolen_goods","reason":"recover loot"}'
                )
            }
        else:
            yield "You secure the stolen goods."

    service = TurnService(
        store,
        model=FunctionModel(reply, stream_function=stream),
        intent=_AlwaysGeneral(),
    )

    stream_events = [
        event async for event in service.stream_turn(session_id, "I take the goods.")
    ]
    state_changed = [
        event
        for event in stream_events
        if isinstance(event, StateChangedEvent) and event.event.get("type") == "item_taken"
    ]
    assert state_changed
    done = next(event for event in stream_events if isinstance(event, DoneEvent))
    assert any(item.id == "stolen_goods" for item in done.state.character.inventory)

    events = await store.list_events(session_id)
    rebuilt = await store.rebuild_snapshot(session_id)
    assert rebuilt == fold_events(events)
    assert rebuilt == done.state

    # Subsequent intent validation sees the taken Item in inventory.
    validation = validate_action_intent(
        rebuilt,
        ProposedActionIntent(kind="use", item_ids=["stolen_goods"], confidence="high"),
    )
    assert validation.ok is True


async def test_after_consume_intent_rejects_exhausted_item(store: EventStore) -> None:
    from dnd_agent.world.intent import validate_action_intent

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=16)
    for _ in range(5):
        await store.append_event(
            state.session_id,
            ItemConsumed(item_id="ration", qty=1, source="inventory", reason="setup"),
        )
    snapshot = await store.get_snapshot(state.session_id)
    assert snapshot is not None
    validation = validate_action_intent(
        snapshot,
        ProposedActionIntent(kind="use", item_ids=["ration"], confidence="high"),
    )
    assert validation.ok is False
    assert "unknown" in validation.reason or "unavailable" in validation.reason


async def test_use_item_non_consumable_validates_without_event(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=17)
    before = await store.get_snapshot(state.session_id)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "use_item",
            {"item_id": "longsword", "reason": "ready steel"},
            "You ready your longsword.",
        ),
        intent=_AlwaysGeneral(),
    )

    result = await service.run_turn(state.session_id, "I ready my longsword.")
    after = await store.get_snapshot(state.session_id)

    assert result.status == "ok"
    assert not any(isinstance(event, ItemConsumed) for event in result.events)
    assert before is not None and after is not None
    assert after.character.inventory == before.character.inventory


async def test_use_item_rejects_missing_stack_without_mutation(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=18)
    for _ in range(5):
        await store.append_event(
            state.session_id,
            ItemConsumed(item_id="ration", qty=1, source="inventory", reason="setup"),
        )
    before = await store.get_snapshot(state.session_id)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "use_item",
            {"item_id": "ration", "reason": "eat air"},
            "There are no rations left.",
        ),
        intent=_AlwaysGeneral(),
    )

    result = await service.run_turn(state.session_id, "I try to eat another ration.")
    after = await store.get_snapshot(state.session_id)

    assert result.status == "ok"
    assert not any(isinstance(event, ItemConsumed) for event in result.events)
    assert before is not None and after is not None
    assert after.character.inventory == before.character.inventory


class _AlwaysGeneral:
    async def propose(self, player_text: str, state: object) -> ProposedActionIntent:
        return ProposedActionIntent(kind="general", confidence="high")


class _AlwaysUseRation:
    async def propose(self, player_text: str, state: object) -> ProposedActionIntent:
        return ProposedActionIntent(
            kind="use",
            item_ids=["ration"],
            confidence="high",
        )
