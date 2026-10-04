"""Seam: DM Agent condition/save/rest tools via FunctionModel."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.domain.events import (
    ConditionAdded,
    ConditionRemoved,
    LongRestCompleted,
    SavingThrowResolved,
    ShortRestCompleted,
)
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "conditions.db")
    await event_store.open()
    return event_store


def _tool_then_narrate(tool_name: str, args: dict, narration: str = "Done.") -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args=args)])
        return ModelResponse(parts=[TextPart(content=narration)])

    return FunctionModel(reply)


async def test_add_and_remove_condition_tools(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "add_condition",
            {"condition": "poisoned", "reason": "swamp gas"},
            "You feel sick.",
        ),
    )
    added = await service.run_turn(state.session_id, "I breathe the fumes.")
    assert any(isinstance(event, ConditionAdded) for event in added.events)
    snapshot = await store.get_snapshot(state.session_id)
    assert snapshot is not None
    assert "poisoned" in snapshot.character.conditions

    service = TurnService(
        store,
        model=_tool_then_narrate(
            "remove_condition",
            {"condition": "poisoned", "reason": "antidote"},
            "The poison fades.",
        ),
    )
    removed = await service.run_turn(state.session_id, "I drink the antidote.")
    assert any(isinstance(event, ConditionRemoved) for event in removed.events)
    snapshot = await store.get_snapshot(state.session_id)
    assert snapshot is not None
    assert snapshot.character.conditions == []


async def test_unknown_condition_rejected_without_event(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=2)
    before = await store.get_snapshot(state.session_id)

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
                        tool_name="add_condition",
                        args={"condition": "on_fire", "reason": "test"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="Nothing happens.")])

    service = TurnService(store, model=FunctionModel(reply))
    result = await service.run_turn(state.session_id, "I try to catch fire.")
    after = await store.get_snapshot(state.session_id)

    assert result.status == "ok"
    assert before is not None and after is not None
    assert after.character.conditions == before.character.conditions
    assert not any(isinstance(event, ConditionAdded) for event in result.events)


async def test_saving_throw_tool_persists_event(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=3)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "saving_throw",
            {"ability": "constitution", "dc": 12, "reason": "poison cloud"},
            "You grit through the nausea.",
        ),
    )
    result = await service.run_turn(state.session_id, "I hold my breath.")
    assert any(isinstance(event, SavingThrowResolved) for event in result.events)
    save = next(event for event in result.events if isinstance(event, SavingThrowResolved))
    assert save.ability == "constitution"
    assert save.dc == 12


async def test_short_and_long_rest_tools(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=4)
    # Damage the character via short-rest setup: add condition then long rest clears it.
    await TurnService(
        store,
        model=_tool_then_narrate(
            "add_condition",
            {"condition": "frightened", "reason": "roar"},
        ),
    ).run_turn(state.session_id, "A roar echoes.")

    # Manually lower HP through a short rest after inventing damage isn't available —
    # short rest with 1 die from full HP still spends a die.
    short = await TurnService(
        store,
        model=_tool_then_narrate(
            "short_rest",
            {"hit_dice_to_spend": 1, "reason": "catch breath"},
            "You catch your breath.",
        ),
    ).run_turn(state.session_id, "I take a short rest.")
    assert any(isinstance(event, ShortRestCompleted) for event in short.events)
    after_short = await store.get_snapshot(state.session_id)
    assert after_short is not None
    assert after_short.character.hit_dice_remaining == 0

    long = await TurnService(
        store,
        model=_tool_then_narrate(
            "long_rest",
            {"reason": "camp overnight"},
            "Dawn breaks.",
        ),
    ).run_turn(state.session_id, "I sleep until morning.")
    assert any(isinstance(event, LongRestCompleted) for event in long.events)
    after_long = await store.get_snapshot(state.session_id)
    assert after_long is not None
    assert after_long.character.hp == after_long.character.max_hp
    assert after_long.character.hit_dice_remaining == 1
    assert after_long.character.conditions == []


async def test_short_rest_rejects_no_hit_dice(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=5)
    await TurnService(
        store,
        model=_tool_then_narrate("short_rest", {"hit_dice_to_spend": 1}),
    ).run_turn(state.session_id, "rest once")
    before = await store.get_snapshot(state.session_id)

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
                        tool_name="short_rest",
                        args={"hit_dice_to_spend": 1, "reason": "again"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="Still tired.")])

    result = await TurnService(store, model=FunctionModel(reply)).run_turn(
        state.session_id, "rest again"
    )
    after = await store.get_snapshot(state.session_id)
    assert result.status == "ok"
    assert before is not None and after is not None
    assert after.character.hit_dice_remaining == before.character.hit_dice_remaining
    assert after.rng_seed == before.rng_seed
    assert not any(isinstance(event, ShortRestCompleted) for event in result.events)
