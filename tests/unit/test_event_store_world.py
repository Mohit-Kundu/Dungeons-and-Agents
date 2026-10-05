"""Seam: EventStore seeds PlayableWorld and lazily upgrades legacy Sessions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from dnd_agent.content.loader import load_character, load_scenario
from dnd_agent.domain.events import SessionCreated, SummaryUpdated
from dnd_agent.domain.models import PlayableWorld, Quest
from dnd_agent.store.event_store import EventStore
from dnd_agent.store.reducer import fold_events


@pytest.fixture
def store(tmp_path: Path) -> EventStore:
    return EventStore(tmp_path / "world.db")


async def test_create_session_seeds_playable_world(store: EventStore) -> None:
    session = await store.create_session(
        scenario_id="goblin_cave",
        character_id="pregen_fighter",
        rng_seed=42,
    )

    loaded = await store.get_snapshot(session.session_id)
    events = await store.list_events(session.session_id)

    assert loaded is not None
    assert loaded.location == "cave_mouth"
    assert loaded.world.is_seeded()
    assert loaded.world.visited_location_ids == ["cave_mouth"]
    assert any(group.id == "den_goblins" for group in loaded.world.enemy_groups)
    assert any(objective.id == "recover_stolen_goods" for objective in loaded.world.objectives)
    assert isinstance(events[0], SessionCreated)
    assert events[0].world.is_seeded()
    assert fold_events(events) == loaded


async def _insert_legacy_session(db_path: Path) -> str:
    """Persist a pre-world SessionCreated payload the way older builds did."""
    scenario = load_scenario("goblin_cave")
    character = load_character("pregen_fighter")
    session_id = "sess_legacy"
    event = SessionCreated(
        session_id=session_id,
        scenario_id=scenario.id,
        character=character,
        location="Cave Mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive the goblins out of the cave.",
            status="active",
        ),
        rng_seed=99,
        summary="Briefing seed from an older build.",
        world=PlayableWorld(),
    )
    # Strip world so the stored JSON matches the previous schema shape.
    payload = json.loads(event.model_dump_json())
    payload.pop("world", None)
    state = {
        "session_id": session_id,
        "scenario_id": scenario.id,
        "character": character.model_dump(mode="json"),
        "location": "Cave Mouth",
        "quest": payload["quest"],
        "rng_seed": 99,
        "summary": "Briefing seed from an older build.",
    }
    now = datetime.now(UTC).isoformat()
    store = EventStore(db_path)
    await store.open()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO sessions (id, scenario_id, created_at) VALUES (?, ?, ?)",
            (session_id, scenario.id, now),
        )
        await db.execute(
            """
            INSERT INTO events (session_id, type, payload_json, ts)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, "session_created", json.dumps(payload), now),
        )
        await db.execute(
            """
            INSERT INTO snapshots (session_id, state_json)
            VALUES (?, ?)
            """,
            (session_id, json.dumps(state)),
        )
        await db.execute(
            """
            INSERT INTO turns (
                session_id, turn_number, player_text, narration, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                1,
                "I peer into the cave.",
                "Torchlight catches muddy tracks.",
                "ok",
                now,
            ),
        )
        await db.commit()
    return session_id


async def test_legacy_session_lazy_upgrade_preserves_turns_and_recap(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy.db"
    session_id = await _insert_legacy_session(db_path)
    store = EventStore(db_path)

    upgraded = await store.get_snapshot(session_id)
    rebuilt = await store.rebuild_snapshot(session_id)
    events = await store.list_events(session_id)
    latest = await store.get_latest_turn(session_id)

    assert upgraded is not None
    assert upgraded.world.is_seeded()
    assert upgraded.location == "cave_mouth"
    assert upgraded.summary == "Briefing seed from an older build."
    assert upgraded.world.visited_location_ids == ["cave_mouth"]
    assert rebuilt == upgraded
    assert len(events) == 1
    assert isinstance(events[0], SessionCreated)
    assert not events[0].world.is_seeded()
    assert latest is not None
    assert latest["player_text"] == "I peer into the cave."


async def test_legacy_upgrade_survives_later_recap_event(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_recap.db"
    session_id = await _insert_legacy_session(db_path)
    store = EventStore(db_path)
    await store.append_event(
        session_id,
        SummaryUpdated(summary="Brynn found goblin tracks near the cave mouth."),
    )

    snapshot = await store.get_snapshot(session_id)
    rebuilt = await store.rebuild_snapshot(session_id)

    assert snapshot is not None
    assert snapshot.summary == "Brynn found goblin tracks near the cave mouth."
    assert snapshot.world.is_seeded()
    assert rebuilt == snapshot
