"""Seam: injectable RngSource / RngFactory for reproducible dice."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.domain.events import (
    DiceRolled,
    SavingThrowResolved,
    ShortRestCompleted,
    SkillCheckResolved,
)
from dnd_agent.rules.dice import DiceRng, RngSource, roll
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


class FixedRng:
    """Deterministic stub: always returns the same value; next_seed is fixed."""

    def __init__(self, seed: int, *, value: int = 7, next_seed: int = 99) -> None:
        self.seed = seed
        self._value = value
        self._next_seed = next_seed

    def randint(self, lo: int, hi: int) -> int:
        return max(lo, min(hi, self._value))

    def next_seed(self) -> int:
        return self._next_seed


def _tool_then_narrate(
    tool_name: str,
    args: dict[str, Any],
    narration: str,
) -> FunctionModel:
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        has_tool_return = any(
            getattr(part, "part_kind", None) == "tool-return"
            for message in messages
            for part in message.parts
        )
        if not has_tool_return:
            return ModelResponse(
                parts=[ToolCallPart(tool_name=tool_name, args=args)]
            )
        return ModelResponse(parts=[TextPart(content=narration)])

    return FunctionModel(reply)


def test_dice_rng_satisfies_rng_source_protocol() -> None:
    rng: RngSource = DiceRng(seed=42)
    assert 1 <= rng.randint(1, 20) <= 20
    assert isinstance(rng.next_seed(), int)


def test_custom_rng_factory_drives_roll() -> None:
    result = roll("1d20", FixedRng(seed=1, value=11))
    assert result.rolls == [11]
    assert result.total == 11


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "rng.db")
    await event_store.open()
    return event_store


async def test_roll_dice_tool_uses_injected_rng_factory(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "roll_dice",
            {"expression": "1d20", "reason": "test"},
            "The die settles.",
        ),
        rng_factory=lambda seed: FixedRng(seed, value=15, next_seed=777),
    )
    result = await service.run_turn(state.session_id, "I roll a die.")

    assert result.status == "ok"
    rolled = next(event for event in result.events if isinstance(event, DiceRolled))
    assert rolled.rolls == [15]
    assert rolled.total == 15
    assert rolled.next_rng_seed == 777

    after = await store.get_snapshot(state.session_id)
    assert after is not None
    assert after.rng_seed == 777


async def test_skill_check_tool_uses_injected_rng_factory(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "skill_check",
            {"skill": "perception", "dc": 10, "reason": "look around"},
            "You notice damp stone.",
        ),
        rng_factory=lambda seed: FixedRng(seed, value=18, next_seed=555),
    )
    result = await service.run_turn(state.session_id, "I look around.")

    assert result.status == "ok"
    check = next(event for event in result.events if isinstance(event, SkillCheckResolved))
    assert check.d20 == 18
    assert check.success is True
    assert check.next_rng_seed == 555


async def test_saving_throw_tool_uses_injected_rng_factory(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "saving_throw",
            {"ability": "dexterity", "dc": 12, "reason": "trip line"},
            "You catch yourself.",
        ),
        rng_factory=lambda seed: FixedRng(seed, value=16, next_seed=444),
    )
    result = await service.run_turn(state.session_id, "I dodge the trip line.")

    assert result.status == "ok"
    save = next(event for event in result.events if isinstance(event, SavingThrowResolved))
    assert save.d20 == 16
    assert save.success is True
    assert save.next_rng_seed == 444


async def test_short_rest_tool_uses_injected_rng_factory(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(
        store,
        model=_tool_then_narrate(
            "short_rest",
            {"hit_dice_to_spend": 1, "reason": "catch breath"},
            "You feel a bit better.",
        ),
        rng_factory=lambda seed: FixedRng(seed, value=8, next_seed=333),
    )
    result = await service.run_turn(state.session_id, "I take a short rest.")

    assert result.status == "ok"
    rest = next(event for event in result.events if isinstance(event, ShortRestCompleted))
    assert rest.hit_dice_rolls == [8]
    assert rest.next_rng_seed == 333


async def test_identical_seed_and_model_outputs_yield_identical_events(
    tmp_path: Path,
) -> None:
    """Reproducibility contract: same seed + same model outputs → same Event payloads.

    Event payloads have no timestamps; DB `ts` columns are out of scope for this compare.
    """

    async def run_once(db_name: str) -> list[dict]:
        event_store = EventStore(
            tmp_path / db_name,
            seed_factory=lambda: 42,
            id_factory=lambda: "sess_repro",
        )
        await event_store.open()
        state = await event_store.create_session(scenario_id="goblin_cave")
        service = TurnService(
            event_store,
            model=_tool_then_narrate(
                "skill_check",
                {
                    "skill": "perception",
                    "dc": 12,
                    "reason": "search the cave mouth",
                },
                "You spot goblin tracks leading deeper into the cave.",
            ),
        )
        result = await service.run_turn(state.session_id, "I search the cave mouth carefully.")
        assert result.status == "ok"
        events = await event_store.list_events(state.session_id)
        payloads = [event.model_dump(mode="json") for event in events]
        for payload in payloads:
            assert "ts" not in payload
        return payloads

    first = await run_once("a.db")
    second = await run_once("b.db")
    assert first == second
    assert first[0]["session_id"] == "sess_repro"
    assert first[0]["rng_seed"] == 42
