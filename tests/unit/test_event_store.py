"""Seam: EventStore creates Sessions, appends Events, loads Snapshots."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_agent.content.loader import load_character, load_scenario
from dnd_agent.domain.events import SessionCreated, SummaryUpdated
from dnd_agent.store.event_store import EventStore
from dnd_agent.store.reducer import fold_events


@pytest.fixture
def store(tmp_path: Path) -> EventStore:
    return EventStore(tmp_path / "test.db")


async def test_create_session_persists_and_reloads_snapshot(store: EventStore) -> None:
    session = await store.create_session(
        scenario_id="goblin_cave",
        character_id="pregen_fighter",
        rng_seed=42,
    )

    loaded = await store.get_snapshot(session.session_id)

    assert loaded is not None
    assert loaded.session_id == session.session_id
    assert loaded.scenario_id == "goblin_cave"
    assert loaded.character.id == "pregen_fighter"
    assert loaded.character.name == "Brynn Ironfoot"
    assert loaded.location == "Cave Mouth"
    assert loaded.quest.id == "clear_cave"
    assert loaded.rng_seed == 42


async def test_replay_events_matches_snapshot(store: EventStore) -> None:
    session = await store.create_session(
        scenario_id="goblin_cave",
        character_id="pregen_fighter",
        rng_seed=99,
    )

    events = await store.list_events(session.session_id)
    snapshot = await store.get_snapshot(session.session_id)

    assert len(events) == 1
    assert isinstance(events[0], SessionCreated)
    assert snapshot is not None
    assert fold_events(events) == snapshot


async def test_summary_updated_persists_and_rebuilds(store: EventStore) -> None:
    session = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    await store.append_event(
        session.session_id,
        SummaryUpdated(summary="Tracks lead into the dark."),
    )

    snapshot = await store.get_snapshot(session.session_id)
    rebuilt = await store.rebuild_snapshot(session.session_id)

    assert snapshot is not None
    assert snapshot.summary == "Tracks lead into the dark."
    assert rebuilt.summary == snapshot.summary


async def test_content_loader_reads_predefined_assets() -> None:
    character = load_character("pregen_fighter")
    scenario = load_scenario("goblin_cave")

    assert character.name == "Brynn Ironfoot"
    assert scenario.id == "goblin_cave"
    assert scenario.character_id == "pregen_fighter"
    assert scenario.starting_location == "Cave Mouth"
