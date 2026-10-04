"""Seam: CLI parses SSE Turn streams into typed payloads."""

from __future__ import annotations

from dnd_agent.cli.sse import iter_sse_data


def test_iter_sse_data_parses_event_blocks() -> None:
    raw = (
        "event: narration_delta\n"
        'data: {"type":"narration_delta","text":"Hello"}\n'
        "\n"
        "event: done\n"
        'data: {"type":"done","turn_number":1,"status":"ok","state":{},"narration":"Hello"}\n'
        "\n"
    )
    events = list(iter_sse_data(raw.splitlines()))
    assert events[0]["type"] == "narration_delta"
    assert events[0]["text"] == "Hello"
    assert events[1]["type"] == "done"
    assert events[1]["turn_number"] == 1
