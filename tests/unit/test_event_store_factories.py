"""Seam: EventStore seed_factory and id_factory for pinned Sessions."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def store_path(tmp_path: Path) -> Path:
    return tmp_path / "factory.db"


async def test_create_session_uses_seed_and_id_factories(store_path: Path) -> None:
    store = EventStore(
        store_path,
        seed_factory=lambda: 12345,
        id_factory=lambda: "sess_pinned",
    )
    await store.open()

    state = await store.create_session(scenario_id="goblin_cave")

    assert state.session_id == "sess_pinned"
    assert state.rng_seed == 12345


async def test_explicit_rng_seed_and_session_id_override_factories(
    store_path: Path,
) -> None:
    store = EventStore(
        store_path,
        seed_factory=lambda: 1,
        id_factory=lambda: "sess_ignored",
    )
    await store.open()

    state = await store.create_session(
        scenario_id="goblin_cave",
        rng_seed=99,
        session_id="sess_explicit",
    )

    assert state.session_id == "sess_explicit"
    assert state.rng_seed == 99


async def test_default_factories_produce_distinct_sessions(store_path: Path) -> None:
    store = EventStore(store_path)
    await store.open()

    first = await store.create_session(scenario_id="goblin_cave")
    second = await store.create_session(scenario_id="goblin_cave")

    assert first.session_id != second.session_id
