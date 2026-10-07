"""Seam: tool_validity_from_messages counts calls and errors."""

from __future__ import annotations

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from dnd_agent.telemetry.meter import tool_validity_from_messages


def test_tool_validity_counts_calls_and_retry_errors() -> None:
    messages = [
        ModelRequest(parts=[UserPromptPart(content="hi")]),
        ModelResponse(
            parts=[ToolCallPart(tool_name="skill_check", args={"skill": "perception", "dc": 10})]
        ),
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="skill_check",
                    content="error: unknown skill",
                    tool_call_id="1",
                )
            ]
        ),
        ModelResponse(parts=[ToolCallPart(tool_name="skill_check", args={"skill": "stealth", "dc": 10})]),
        ModelRequest(parts=[RetryPromptPart(content="fix failed", tool_name="skill_check")]),
        ModelResponse(parts=[TextPart(content="ok")]),
    ]
    calls, errors = tool_validity_from_messages(messages)
    assert calls == 2
    assert errors == 2
