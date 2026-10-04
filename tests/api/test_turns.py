"""Seam: HTTP playable Turn endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.api.app import create_app
from dnd_agent.store.event_store import EventStore


def _scripted_model() -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="skill_check",
                        args={"skill": "investigation", "dc": 11, "reason": "search"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="You notice scratches on the stone.")])

    return FunctionModel(reply)


@pytest.fixture
async def client(tmp_path: Path):
    store = EventStore(tmp_path / "turns_api.db")
    await store.open()
    app = create_app(store=store, turn_model=_scripted_model())
    app.state.store = store
    app.state.turn_model = _scripted_model()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_play_turn_returns_narration_and_events(client: AsyncClient) -> None:
    created = await client.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 3})
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/sessions/{session_id}/turns",
        json={"player_text": "I search the room."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "scratches" in body["narration"].lower()
    assert any(event["type"] == "skill_check_resolved" for event in body["events"])
    assert body["state"]["session_id"] == session_id


def _condition_model() -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="add_condition",
                        args={"condition": "poisoned", "reason": "venom"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="Venom burns in your veins.")])

    return FunctionModel(reply)


def _save_model() -> FunctionModel:
    calls = {"n": 0}

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="saving_throw",
                        args={"ability": "constitution", "dc": 12, "reason": "toxin"},
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content="You shake off the toxin.")])

    return FunctionModel(reply)


async def test_play_turn_persists_saving_throw_event(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "save_api.db")
    await store.open()
    model = _save_model()
    app = create_app(store=store, turn_model=model)
    app.state.store = store
    app.state.turn_model = model
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 8}
        )
        session_id = created.json()["session_id"]
        response = await client.post(
            f"/sessions/{session_id}/turns",
            json={"player_text": "I resist the toxin."},
        )

    assert response.status_code == 200
    body = response.json()
    assert any(event["type"] == "saving_throw_resolved" for event in body["events"])


async def test_play_turn_persists_condition_event(tmp_path: Path) -> None:
    store = EventStore(tmp_path / "condition_api.db")
    await store.open()
    model = _condition_model()
    app = create_app(store=store, turn_model=model)
    app.state.store = store
    app.state.turn_model = model
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 9}
        )
        session_id = created.json()["session_id"]
        response = await client.post(
            f"/sessions/{session_id}/turns",
            json={"player_text": "A spider bites me."},
        )

    assert response.status_code == 200
    body = response.json()
    assert any(event["type"] == "condition_added" for event in body["events"])
    assert "poisoned" in body["state"]["character"]["conditions"]
