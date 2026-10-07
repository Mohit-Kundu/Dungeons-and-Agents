"""Seam: MeteredModel + TurnMeter at the PydanticAI Model boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from dnd_agent.telemetry.meter import (
    MeteredModel,
    begin_turn_meter,
    get_turn_meter,
    safe_response_cost_usd,
)


def _echo_model() -> FunctionModel:
    def reply(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        last = messages[-1]
        assert isinstance(last, ModelRequest)
        part = last.parts[0]
        assert isinstance(part, UserPromptPart)
        return ModelResponse(
            parts=[TextPart(content=f"echo:{part.content}")],
            usage=RequestUsage(input_tokens=11, output_tokens=7),
            model_name="test-echo-model",
        )

    return FunctionModel(reply)


async def test_metered_model_records_tokens_and_role() -> None:
    meter = begin_turn_meter()
    model = MeteredModel(_echo_model(), role="dm")
    params = ModelRequestParameters()
    await model.request(
        [ModelRequest(parts=[UserPromptPart(content="hello")])],
        None,
        params,
    )
    assert len(meter.requests) == 1
    record = meter.requests[0]
    assert record.role == "dm"
    assert record.model_name  # FunctionModel may override ModelResponse.model_name
    assert record.input_tokens == 11
    assert record.output_tokens == 7
    assert record.latency_ms >= 0
    assert get_turn_meter() is meter


def test_safe_response_cost_unknown_model_is_none() -> None:
    response = ModelResponse(
        parts=[TextPart(content="x")],
        usage=RequestUsage(input_tokens=10, output_tokens=5),
        model_name="totally-unknown-xyz",
    )
    assert safe_response_cost_usd(response) is None


def test_safe_response_cost_known_model_is_float() -> None:
    response = ModelResponse(
        parts=[TextPart(content="x")],
        usage=RequestUsage(input_tokens=1000, output_tokens=500),
        model_name="gemini-2.5-flash",
    )
    cost = safe_response_cost_usd(response)
    assert cost is not None
    assert cost >= 0
