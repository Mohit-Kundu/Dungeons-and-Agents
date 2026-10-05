"""Seam: GET overview / POST recap refresh Recaps lazily."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.api.app import create_app
from dnd_agent.store.event_store import EventStore


def _recap_model(text: str = "Brynn found muddy goblin tracks.") -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        return ModelResponse(parts=[TextPart(content=text)])

    model = FunctionModel(reply)
    model.calls = calls  # type: ignore[attr-defined]
    return model


@pytest.fixture
async def client(tmp_path: Path):
    store = EventStore(tmp_path / "overview.db")
    await store.open()
    model = _recap_model()
    app = create_app(store=store, recap_model=model)
    app.state.store = store
    app.state.recap_model = model
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, store, model


async def test_overview_refreshes_played_session(
    client: tuple[AsyncClient, EventStore, FunctionModel],
) -> None:
    ac, store, model = client
    created = await ac.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 2})
    session_id = created.json()["session_id"]
    await store.add_turn(
        session_id,
        player_text="I search the mouth of the cave.",
        narration="You find muddy goblin tracks.",
        status="ok",
    )

    response = await ac.get(f"/sessions/{session_id}/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["refreshed"] is True
    assert body["state"]["summary"] == "Brynn found muddy goblin tracks."
    assert body["state"]["recap_through_turn"] == 1
    assert body["latest_turn"]["turn_number"] == 1
    assert body["latest_turn"]["player_text"] == "I search the mouth of the cave."
    assert body["latest_turn"]["narration"] == "You find muddy goblin tracks."
    assert body["latest_turn"]["status"] == "ok"
    assert model.calls["n"] == 1  # type: ignore[attr-defined]


async def test_overview_without_turns_skips_model(
    client: tuple[AsyncClient, EventStore, FunctionModel],
) -> None:
    ac, _store, model = client
    created = await ac.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 2})
    session_id = created.json()["session_id"]

    response = await ac.get(f"/sessions/{session_id}/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["latest_turn"] is None
    assert body["refreshed"] is False
    assert model.calls["n"] == 0  # type: ignore[attr-defined]
    assert "Goblin" in body["state"]["summary"] or body["state"]["summary"]


async def test_post_recap_command_refreshes(
    client: tuple[AsyncClient, EventStore, FunctionModel],
) -> None:
    ac, store, model = client
    created = await ac.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 3})
    session_id = created.json()["session_id"]
    await store.add_turn(
        session_id,
        player_text="I listen.",
        narration="Dripping water echoes.",
        status="ok",
    )

    response = await ac.post(f"/sessions/{session_id}/recap")
    assert response.status_code == 200
    body = response.json()
    assert body["refreshed"] is True
    assert body["failed"] is False
    assert body["state"]["recap_through_turn"] == 1
    assert model.calls["n"] == 1  # type: ignore[attr-defined]


async def test_in_play_slash_recap_refreshes_without_turn(
    client: tuple[AsyncClient, EventStore, FunctionModel],
) -> None:
    ac, store, model = client
    created = await ac.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 4})
    session_id = created.json()["session_id"]
    await store.add_turn(
        session_id,
        player_text="I wait.",
        narration="Time passes.",
        status="ok",
    )

    response = await ac.post(
        f"/sessions/{session_id}/turns",
        json={"player_text": "/recap"},
    )
    assert response.status_code == 200
    assert "text/event-stream" not in response.headers.get("content-type", "")
    body = response.json()
    assert body["refreshed"] is True
    assert body["state"]["recap_through_turn"] == 1
    turns = await store.list_recent_turns(session_id, limit=10)
    assert len(turns) == 1
    assert model.calls["n"] == 1  # type: ignore[attr-defined]


async def test_overview_failure_keeps_prior_recap(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "fail.db")
    await store.open()

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError("down")

    app = create_app(store=store, recap_model=FunctionModel(reply))
    app.state.store = store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        created = await ac.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 5})
        session_id = created.json()["session_id"]
        prior = created.json()["summary"]
        await store.add_turn(
            session_id,
            player_text="I search.",
            narration="Tracks.",
            status="ok",
        )
        response = await ac.get(f"/sessions/{session_id}/overview")
        body = response.json()
        assert body["refreshed"] is False
        assert body["refresh_failed"] is True
        assert body["state"]["summary"] == prior
        assert body["latest_turn"]["turn_number"] == 1
