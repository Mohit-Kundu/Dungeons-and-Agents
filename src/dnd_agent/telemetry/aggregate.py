"""Aggregate Turn Telemetry for eval runs and reporting."""

from __future__ import annotations

import statistics
from typing import Literal

from pydantic import BaseModel, Field

TurnStatus = Literal["ok", "no_progress", "aborted"]


class ModelRequestTelemetry(BaseModel):
    role: str
    model_name: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float | None = None


class TurnTelemetry(BaseModel):
    session_id: str
    turn_number: int
    status: TurnStatus
    latency_ms: float
    input_tokens: int
    output_tokens: int
    tool_calls: int
    tool_errors: int
    cost_usd: float | None = None
    unknown_pricing_count: int = 0
    model_requests: list[ModelRequestTelemetry] = Field(default_factory=list)


class SessionMetrics(BaseModel):
    turn_count: int
    no_progress_count: int
    no_progress_rate: float
    total_input_tokens: int
    total_output_tokens: int
    total_tool_calls: int
    total_tool_errors: int
    tool_validity_rate: float | None
    latency_ms_p50: float | None
    latency_ms_p95: float | None
    cost_usd_total: float | None
    unknown_pricing_count: int


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("empty values")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def aggregate_turn_metrics(rows: list[TurnTelemetry]) -> SessionMetrics:
    """Summarize per-Turn telemetry for eval reports."""
    turn_count = len(rows)
    no_progress_count = sum(1 for row in rows if row.status == "no_progress")
    no_progress_rate = no_progress_count / turn_count if turn_count else 0.0

    total_input = sum(row.input_tokens for row in rows)
    total_output = sum(row.output_tokens for row in rows)
    total_tool_calls = sum(row.tool_calls for row in rows)
    total_tool_errors = sum(row.tool_errors for row in rows)
    if total_tool_calls:
        tool_validity_rate = (total_tool_calls - total_tool_errors) / total_tool_calls
    else:
        tool_validity_rate = None

    latencies = [row.latency_ms for row in rows]
    latency_p50 = statistics.median(latencies) if latencies else None
    latency_p95 = _percentile(latencies, 0.95) if latencies else None

    unknown_pricing_count = sum(row.unknown_pricing_count for row in rows)
    known_costs = [row.cost_usd for row in rows if row.cost_usd is not None]
    if any(row.cost_usd is None for row in rows) and not known_costs:
        cost_total: float | None = None
    elif any(row.cost_usd is None for row in rows):
        cost_total = sum(known_costs)
    else:
        cost_total = sum(known_costs) if known_costs else 0.0

    return SessionMetrics(
        turn_count=turn_count,
        no_progress_count=no_progress_count,
        no_progress_rate=no_progress_rate,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tool_calls=total_tool_calls,
        total_tool_errors=total_tool_errors,
        tool_validity_rate=tool_validity_rate,
        latency_ms_p50=latency_p50,
        latency_ms_p95=latency_p95,
        cost_usd_total=cost_total,
        unknown_pricing_count=unknown_pricing_count,
    )
