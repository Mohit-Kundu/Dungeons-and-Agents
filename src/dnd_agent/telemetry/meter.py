"""MeteredModel and per-Turn usage collection."""

from __future__ import annotations

import contextvars
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import RunContext

from dnd_agent.agent.cassette import ModelRole
from dnd_agent.telemetry.aggregate import ModelRequestTelemetry, TurnStatus, TurnTelemetry

_turn_meter: contextvars.ContextVar[TurnMeter | None] = contextvars.ContextVar(
    "turn_meter",
    default=None,
)


def safe_response_cost_usd(response: ModelResponse) -> float | None:
    """Return USD cost from genai-prices, or None when pricing is unknown."""
    if not response.model_name:
        return None
    try:
        calc = response.cost()
        return float(calc.total_price)
    except (LookupError, ValueError, AssertionError):
        return None


@dataclass
class ModelRequestRecord:
    role: ModelRole
    model_name: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


@dataclass
class TurnMeter:
    """Collects model requests and timing for one Turn."""

    started_at: float = field(default_factory=time.perf_counter)
    requests: list[ModelRequestRecord] = field(default_factory=list)

    def record_response(
        self,
        *,
        role: ModelRole,
        response: ModelResponse,
        latency_ms: float,
    ) -> None:
        usage = response.usage
        self.requests.append(
            ModelRequestRecord(
                role=role,
                model_name=response.model_name or "",
                latency_ms=latency_ms,
                input_tokens=int(usage.input_tokens or 0),
                output_tokens=int(usage.output_tokens or 0),
                cost_usd=safe_response_cost_usd(response),
            )
        )

    @property
    def latency_ms(self) -> float:
        return (time.perf_counter() - self.started_at) * 1000.0

    def totals(self) -> tuple[int, int, float | None, int]:
        """input_tokens, output_tokens, cost_usd sum (None if any unknown), unknown_pricing_count."""
        input_tokens = sum(r.input_tokens for r in self.requests)
        output_tokens = sum(r.output_tokens for r in self.requests)
        unknown = sum(1 for r in self.requests if r.cost_usd is None)
        known_costs = [r.cost_usd for r in self.requests if r.cost_usd is not None]
        cost_total: float | None
        if unknown and not known_costs:
            cost_total = None
        elif unknown:
            cost_total = sum(known_costs)
        else:
            cost_total = sum(known_costs) if known_costs else 0.0
        return input_tokens, output_tokens, cost_total, unknown


def begin_turn_meter() -> TurnMeter:
    meter = TurnMeter()
    _turn_meter.set(meter)
    return meter


def get_turn_meter() -> TurnMeter | None:
    return _turn_meter.get()


def meter_model(model: Model, *, role: ModelRole) -> Model:
    if isinstance(model, MeteredModel):
        return model
    return MeteredModel(model, role=role)


def build_turn_telemetry(
    session_id: str,
    turn_number: int,
    status: TurnStatus,
    *,
    tool_calls: int,
    tool_errors: int,
) -> TurnTelemetry:
    meter = get_turn_meter()
    if meter is None:
        return TurnTelemetry(
            session_id=session_id,
            turn_number=turn_number,
            status=status,
            latency_ms=0.0,
            input_tokens=0,
            output_tokens=0,
            tool_calls=tool_calls,
            tool_errors=tool_errors,
            cost_usd=None,
            unknown_pricing_count=0,
        )
    input_tokens, output_tokens, cost_usd, unknown = meter.totals()
    model_requests = [
        ModelRequestTelemetry(
            role=record.role,
            model_name=record.model_name,
            latency_ms=record.latency_ms,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            cost_usd=record.cost_usd,
        )
        for record in meter.requests
    ]
    return TurnTelemetry(
        session_id=session_id,
        turn_number=turn_number,
        status=status,
        latency_ms=meter.latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_calls=tool_calls,
        tool_errors=tool_errors,
        cost_usd=cost_usd,
        unknown_pricing_count=unknown,
        model_requests=model_requests,
    )


def tool_validity_from_messages(messages: list[ModelMessage]) -> tuple[int, int]:
    """Return (tool_calls, tool_errors) from agent message history."""
    tool_calls = 0
    tool_errors = 0
    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                tool_calls += 1
            elif isinstance(part, RetryPromptPart):
                tool_errors += 1
            elif isinstance(part, ToolReturnPart):
                if part.outcome != "success":
                    tool_errors += 1
                elif isinstance(part.content, str) and "error" in part.content.lower():
                    tool_errors += 1
    return tool_calls, tool_errors


class MeteredModel(WrapperModel):
    """Wrap a Model and append usage records to the active TurnMeter."""

    _role: ModelRole

    def __init__(self, wrapped: Model, *, role: ModelRole) -> None:
        super().__init__(wrapped)
        self._role = role

    @property
    def role(self) -> ModelRole:
        return self._role

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        start = time.perf_counter()
        response = await self.wrapped.request(
            messages, model_settings, model_request_parameters
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        meter = get_turn_meter()
        if meter is not None:
            meter.record_response(role=self._role, response=response, latency_ms=latency_ms)
        return response

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ):
        start = time.perf_counter()
        async with self.wrapped.request_stream(
            messages, model_settings, model_request_parameters, run_context
        ) as stream:
            try:
                yield stream
            finally:
                latency_ms = (time.perf_counter() - start) * 1000.0
                meter = get_turn_meter()
                if meter is not None:
                    try:
                        response = stream.get()
                    except Exception:  # noqa: BLE001 - partial stream
                        response = None
                    if response is not None:
                        meter.record_response(
                            role=self._role,
                            response=response,
                            latency_ms=latency_ms,
                        )
