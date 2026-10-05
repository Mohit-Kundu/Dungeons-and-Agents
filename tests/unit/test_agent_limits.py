"""Seam: agent retries and Turn usage limits come from Settings."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from dnd_agent.agent.dm_agent import build_dm_agent
from dnd_agent.config import Settings
from dnd_agent.services.stream_events import DoneEvent, ErrorEvent
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore


async def _reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content="ok")])


def test_build_dm_agent_uses_retries_setting() -> None:
    agent = build_dm_agent(FunctionModel(_reply), retries=5)
    assert agent._max_tool_retries == 5  # noqa: SLF001
    assert agent._max_output_retries == 5  # noqa: SLF001


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "limits.db")
    await event_store.open()
    return event_store


def _runaway_tool_model() -> FunctionModel:
    """Always requests another skill_check (never narrates)."""

    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="skill_check",
                    args={"skill": "perception", "dc": 10, "reason": "loop"},
                )
            ]
        )

    async def stream(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[dict[int, DeltaToolCall]]:
        yield {0: DeltaToolCall(name="skill_check")}
        yield {
            0: DeltaToolCall(
                json_args='{"skill":"perception","dc":10,"reason":"loop"}'
            )
        }

    return FunctionModel(reply, stream_function=stream)


async def test_tool_call_limit_aborts_runaway_turn(store: EventStore) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    settings = Settings(
        model="google-gla:gemini-2.5-flash",
        gemini_api_key="unused",
        max_tool_calls_per_turn=1,
        agent_retries=0,
    )
    service = TurnService(store, settings=settings, model=_runaway_tool_model())

    events = [
        event async for event in service.stream_turn(state.session_id, "I look forever.")
    ]

    assert any(isinstance(event, ErrorEvent) for event in events)
    done = next(event for event in events if isinstance(event, DoneEvent))
    assert done.status == "aborted"
