"""Seam: EventStore turn_metrics persistence (separate from Events)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_agent.store.event_store import EventStore
from dnd_agent.telemetry.aggregate import ModelRequestTelemetry, TurnTelemetry


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "metrics.db")
    await event_store.open()
    return event_store


async def test_add_and_list_turn_metrics_survives_reopen(tmp_path: Path, store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1, session_id="sess_metrics")
    await store.add_turn(
        state.session_id,
        player_text="hi",
        narration="hello",
        status="ok",
    )
    telemetry = TurnTelemetry(
        session_id=state.session_id,
        turn_number=1,
        status="ok",
        latency_ms=42.5,
        input_tokens=10,
        output_tokens=5,
        tool_calls=2,
        tool_errors=1,
        cost_usd=0.001,
        unknown_pricing_count=0,
        model_requests=[
            ModelRequestTelemetry(
                role="dm",
                model_name="test",
                latency_ms=40.0,
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
            )
        ],
    )
    await store.add_turn_metrics(state.session_id, 1, telemetry)

    rows = await store.list_turn_metrics(state.session_id)
    assert len(rows) == 1
    assert rows[0].turn_number == 1
    assert rows[0].tool_calls == 2
    assert rows[0].cost_usd == pytest.approx(0.001)

    events = await store.list_events(state.session_id)
    assert len(events) == 1
    assert events[0].type == "session_created"

    db_path = tmp_path / "metrics.db"
    reopened = EventStore(db_path)
    await reopened.open()
    again = await reopened.list_turn_metrics(state.session_id)
    assert len(again) == 1
    assert again[0].input_tokens == 10
