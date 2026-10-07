"""Seam: aggregate_turn_metrics for eval reporting."""

from __future__ import annotations

from dnd_agent.telemetry.aggregate import TurnTelemetry, aggregate_turn_metrics


def test_aggregate_sums_cost_and_counts_unknown_pricing() -> None:
    rows = [
        TurnTelemetry(
            session_id="s",
            turn_number=1,
            status="ok",
            latency_ms=100.0,
            input_tokens=10,
            output_tokens=5,
            tool_calls=4,
            tool_errors=1,
            cost_usd=0.01,
            unknown_pricing_count=0,
        ),
        TurnTelemetry(
            session_id="s",
            turn_number=2,
            status="no_progress",
            latency_ms=200.0,
            input_tokens=3,
            output_tokens=1,
            tool_calls=0,
            tool_errors=0,
            cost_usd=None,
            unknown_pricing_count=1,
        ),
    ]
    metrics = aggregate_turn_metrics(rows)
    assert metrics.turn_count == 2
    assert metrics.no_progress_count == 1
    assert metrics.no_progress_rate == 0.5
    assert metrics.total_input_tokens == 13
    assert metrics.total_tool_calls == 4
    assert metrics.total_tool_errors == 1
    assert metrics.tool_validity_rate == 0.75
    assert metrics.cost_usd_total == 0.01
    assert metrics.unknown_pricing_count == 1
    assert metrics.latency_ms_p50 == 150.0
