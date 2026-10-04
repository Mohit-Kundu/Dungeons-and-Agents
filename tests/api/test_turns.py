"""Seam: HTTP playable Turn endpoint (SSE)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from dnd_agent.api.app import create_app
from dnd_agent.cli.sse import iter_sse_data
from dnd_agent.store.event_store import EventStore


def _parse_sse(body: str) -> list[dict]:
    return list(iter_sse_data(body.splitlines()))


def _done_payload(events: list[dict]) -> dict:
    done = next(event for event in events if event["type"] == "done")
    return done


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

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        calls["n"] += 1
        if calls["n"] == 1:
            yield {0: DeltaToolCall(name="skill_check")}
            yield {
                0: DeltaToolCall(
                    json_args='{"skill":"investigation","dc":11,"reason":"search"}'
                )
            }
        else:
            yield "You notice scratches on the stone."

    return FunctionModel(reply, stream_function=stream)


@pytest.fixture
async def client(tmp_path: Path):
    store = EventStore(tmp_path / "turns_api.db")
    await store.open()
    model = _scripted_model()
    app = create_app(store=store, turn_model=model)
    app.state.store = store
    app.state.turn_model = model
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
    assert "text/event-stream" in response.headers["content-type"]
    events = _parse_sse(response.text)
    done = _done_payload(events)
    assert done["status"] == "ok"
    narration = "".join(
        event["text"] for event in events if event["type"] == "narration_delta"
    )
    assert "scratches" in narration.lower()
    assert any(event["type"] == "roll" for event in events)
    assert done["state"]["session_id"] == session_id


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

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        calls["n"] += 1
        if calls["n"] == 1:
            yield {0: DeltaToolCall(name="add_condition")}
            yield {0: DeltaToolCall(json_args='{"condition":"poisoned","reason":"venom"}')}
        else:
            yield "Venom burns in your veins."

    return FunctionModel(reply, stream_function=stream)


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

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        calls["n"] += 1
        if calls["n"] == 1:
            yield {0: DeltaToolCall(name="saving_throw")}
            yield {
                0: DeltaToolCall(
                    json_args='{"ability":"constitution","dc":12,"reason":"toxin"}'
                )
            }
        else:
            yield "You shake off the toxin."

    return FunctionModel(reply, stream_function=stream)


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
    events = _parse_sse(response.text)
    assert any(
        event["type"] == "roll" and event["event"]["type"] == "saving_throw_resolved"
        for event in events
    )


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
    events = _parse_sse(response.text)
    done = _done_payload(events)
    assert any(event["type"] == "state_changed" for event in events)
    assert "poisoned" in done["state"]["character"]["conditions"]
