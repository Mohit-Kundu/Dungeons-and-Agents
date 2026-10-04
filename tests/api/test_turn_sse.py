"""Seam: POST /turns streams SSE event types from D-005."""

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


def _streaming_model() -> FunctionModel:
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
            text = "You notice scratches on the stone."
            for index in range(0, len(text), 10):
                yield text[index : index + 10]

    return FunctionModel(reply, stream_function=stream)


@pytest.fixture
async def client(tmp_path: Path):
    store = EventStore(tmp_path / "sse.db")
    await store.open()
    model = _streaming_model()
    app = create_app(store=store, turn_model=model)
    app.state.store = store
    app.state.turn_model = model
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_play_turn_streams_sse_contract(client: AsyncClient) -> None:
    created = await client.post("/sessions", json={"scenario_id": "goblin_cave", "rng_seed": 3})
    session_id = created.json()["session_id"]

    response = await client.post(
        f"/sessions/{session_id}/turns",
        json={"player_text": "I search the room."},
    )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = _parse_sse(response.text)
    types = [event["type"] for event in events]
    assert "tool_call" in types
    assert "roll" in types
    assert "narration_delta" in types
    assert types[-1] == "done"
    done = events[-1]
    assert done["status"] == "ok"
    assert "scratches" in "".join(
        event["text"] for event in events if event["type"] == "narration_delta"
    )
