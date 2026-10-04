"""Seam: HTTP session create/state/events."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from dnd_agent.api.app import create_app
from dnd_agent.store.event_store import EventStore


@pytest.fixture
async def client(tmp_path: Path):
    store = EventStore(tmp_path / "api.db")
    await store.open()
    app = create_app(store=store)
    # httpx ASGITransport does not run lifespan; inject store for tests.
    app.state.store = store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_create_session_returns_snapshot(client: AsyncClient) -> None:
    response = await client.post(
        "/sessions",
        json={"scenario_id": "goblin_cave", "rng_seed": 42},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["scenario_id"] == "goblin_cave"
    assert body["character"]["name"] == "Brynn Ironfoot"
    assert body["location"] == "Cave Mouth"
    assert body["rng_seed"] == 42
    assert body["session_id"].startswith("sess_")


async def test_get_state_and_events(client: AsyncClient) -> None:
    created = await client.post("/sessions", json={"scenario_id": "goblin_cave"})
    session_id = created.json()["session_id"]

    state = await client.get(f"/sessions/{session_id}/state")
    events = await client.get(f"/sessions/{session_id}/events")

    assert state.status_code == 200
    assert state.json()["session_id"] == session_id
    assert events.status_code == 200
    payload = events.json()
    assert len(payload["events"]) == 1
    assert payload["events"][0]["type"] == "session_created"


async def test_missing_session_returns_404(client: AsyncClient) -> None:
    response = await client.get("/sessions/sess_missing/state")
    assert response.status_code == 404
