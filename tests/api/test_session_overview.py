"""Seam: GET /sessions/{id}/overview returns Recap + latest Turn."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from dnd_agent.api.app import create_app
from dnd_agent.domain.events import SummaryUpdated
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def client(tmp_path: Path):
    store = EventStore(tmp_path / "overview.db")
    await store.open()
    app = create_app(store=store)
    app.state.store = store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, store


async def test_overview_includes_recap_and_latest_turn(
    client: tuple[AsyncClient, EventStore],
) -> None:
    ac, store = client
    created = await ac.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 2})
    session_id = created.json()["session_id"]

    await store.add_turn(
        session_id,
        player_text="I search the mouth of the cave.",
        narration="You find muddy goblin tracks.",
        status="ok",
    )
    await store.append_event(
        session_id,
        SummaryUpdated(summary="Brynn found muddy goblin tracks at the cave mouth."),
    )

    response = await ac.get(f"/sessions/{session_id}/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["state"]["summary"] == "Brynn found muddy goblin tracks at the cave mouth."
    assert body["latest_turn"]["turn_number"] == 1
    assert body["latest_turn"]["player_text"] == "I search the mouth of the cave."
    assert body["latest_turn"]["narration"] == "You find muddy goblin tracks."
    assert body["latest_turn"]["status"] == "ok"


async def test_overview_without_turns_has_null_latest(
    client: tuple[AsyncClient, EventStore],
) -> None:
    ac, _store = client
    created = await ac.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 2})
    session_id = created.json()["session_id"]

    response = await ac.get(f"/sessions/{session_id}/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["latest_turn"] is None
    assert "Goblin" in body["state"]["summary"] or body["state"]["summary"]
