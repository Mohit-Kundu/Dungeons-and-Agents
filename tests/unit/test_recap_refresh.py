"""Seam: RecapRefreshService folds successful Turns after the watermark."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.agent.recap import RecapService
from dnd_agent.domain.events import SummaryUpdated
from dnd_agent.services.recap_refresh import RecapRefreshResult, RecapRefreshService
from dnd_agent.services.session_locks import SessionLockRegistry
from dnd_agent.store.event_store import EventStore
from dnd_agent.store.reducer import fold_events


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "recap_refresh.db")
    await event_store.open()
    return event_store


def _recap_model(text: str) -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        return ModelResponse(parts=[TextPart(content=text)])

    model = FunctionModel(reply)
    model.calls = calls  # type: ignore[attr-defined]
    return model


def _failing_recap_model() -> FunctionModel:
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError("recap model unavailable")

    return FunctionModel(reply)


async def _seed_ok_turns(store: EventStore, session_id: str, count: int) -> None:
    for index in range(1, count + 1):
        await store.add_turn(
            session_id,
            player_text=f"action {index}",
            narration=f"narration {index}",
            status="ok",
        )


async def test_refresh_summarizes_successful_turns_and_advances_watermark(
    store: EventStore,
) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    await _seed_ok_turns(store, state.session_id, 2)
    await store.add_turn(
        state.session_id,
        player_text="failed swing",
        narration="You miss.",
        status="aborted",
    )
    model = _recap_model("Brynn searched the cave mouth and found tracks.")
    service = RecapRefreshService(store, recap=RecapService(model))

    result = await service.refresh(state.session_id)

    assert result.refreshed is True
    assert result.state.summary == "Brynn searched the cave mouth and found tracks."
    assert result.state.recap_through_turn == 2  # aborted turn 3 ignored
    assert model.calls["n"] == 1  # type: ignore[attr-defined]

    events = await store.list_events(state.session_id)
    updated = next(event for event in events if isinstance(event, SummaryUpdated))
    assert updated.through_turn == 2
    assert updated.reason == "lazy_recap"
    rebuilt = fold_events(events)
    assert rebuilt.summary == result.state.summary
    assert rebuilt.recap_through_turn == 2


async def test_repeated_refresh_is_noop_without_model_call(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=2)
    await _seed_ok_turns(store, state.session_id, 1)
    model = _recap_model("First recap.")
    service = RecapRefreshService(store, recap=RecapService(model))

    first = await service.refresh(state.session_id)
    second = await service.refresh(state.session_id)

    assert first.refreshed is True
    assert second.refreshed is False
    assert second.state.summary == first.state.summary
    assert model.calls["n"] == 1  # type: ignore[attr-defined]


async def test_new_session_with_no_turns_skips_model(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=3)
    prior = state.summary
    model = _recap_model("should not write")
    service = RecapRefreshService(store, recap=RecapService(model))

    result = await service.refresh(state.session_id)

    assert result.refreshed is False
    assert result.state.summary == prior
    assert model.calls["n"] == 0  # type: ignore[attr-defined]


async def test_refresh_failure_preserves_last_good_recap(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=4)
    await _seed_ok_turns(store, state.session_id, 1)
    prior = state.summary
    service = RecapRefreshService(store, recap=RecapService(_failing_recap_model()))

    result = await service.refresh(state.session_id)

    assert result.refreshed is False
    assert result.failed is True
    assert result.state.summary == prior
    assert result.state.recap_through_turn == 0
    events = await store.list_events(state.session_id)
    assert not any(isinstance(event, SummaryUpdated) for event in events)


async def test_incremental_refresh_only_folds_turns_after_watermark(
    store: EventStore,
) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=5)
    await _seed_ok_turns(store, state.session_id, 1)
    await store.append_event(
        state.session_id,
        SummaryUpdated(
            summary="Prior recap covers turn 1.",
            through_turn=1,
            reason="lazy_recap",
        ),
    )
    await store.add_turn(
        state.session_id,
        player_text="I enter the tunnel.",
        narration="The tunnel is wet.",
        status="ok",
    )

    seen: dict[str, str] = {}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        for message in reversed(messages):
            for part in message.parts:
                content = getattr(part, "content", None)
                if isinstance(content, str) and "Pending successful Turns" in content:
                    seen["prompt"] = content
                    break
        return ModelResponse(parts=[TextPart(content="Updated after the tunnel.")])

    service = RecapRefreshService(store, recap=RecapService(FunctionModel(reply)))
    result = await service.refresh(state.session_id)

    assert result.refreshed is True
    assert result.state.recap_through_turn == 2
    assert "action 1" not in seen["prompt"]
    assert "I enter the tunnel." in seen["prompt"]
    assert "Prior Recap" in seen["prompt"]
    assert "Prior recap covers turn 1." in seen["prompt"]


async def test_refresh_lock_serializes_concurrent_calls(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=6)
    await _seed_ok_turns(store, state.session_id, 1)
    active = 0
    max_active = 0

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        active -= 1
        return ModelResponse(parts=[TextPart(content="Locked recap.")])

    locks = SessionLockRegistry()
    service_a = RecapRefreshService(
        store, recap=RecapService(FunctionModel(reply)), locks=locks
    )
    service_b = RecapRefreshService(
        store, recap=RecapService(FunctionModel(reply)), locks=locks
    )

    results = await asyncio.gather(
        service_a.refresh(state.session_id),
        service_b.refresh(state.session_id),
    )
    assert max_active == 1
    assert sum(1 for item in results if item.refreshed) == 1
    snapshot = await store.get_snapshot(state.session_id)
    assert snapshot is not None
    assert snapshot.recap_through_turn == 1
