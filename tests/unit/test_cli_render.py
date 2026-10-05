"""Seam: CLI formats condition/save/rest Events for display."""

from __future__ import annotations

from dnd_agent.api.schemas import LatestTurn
from dnd_agent.cli.render import (
    format_latest_turn,
    format_stream_event,
    format_turn_event,
    progress_status_text,
)


def test_format_saving_throw_event() -> None:
    text = format_turn_event(
        {
            "type": "saving_throw_resolved",
            "ability": "constitution",
            "d20": 14,
            "modifier": 2,
            "total": 16,
            "dc": 13,
            "success": True,
        }
    )
    assert "Save" in text or "Constitution" in text
    assert "SUCCESS" in text


def test_format_condition_and_rest_events() -> None:
    assert "+poisoned" in format_turn_event(
        {"type": "condition_added", "condition": "poisoned", "reason": "gas"}
    )
    assert "-poisoned" in format_turn_event(
        {"type": "condition_removed", "condition": "poisoned", "reason": "cure"}
    )
    short = format_turn_event(
        {
            "type": "short_rest_completed",
            "hit_dice_spent": 1,
            "hit_dice_rolls": [8],
            "hp_recovered": 10,
            "hp_after": 12,
            "hit_dice_remaining": 0,
        }
    )
    assert "Short rest" in short
    assert "10 HP" in short
    long = format_turn_event(
        {
            "type": "long_rest_completed",
            "hp_after": 12,
            "hit_dice_restored": 1,
            "hit_dice_remaining": 1,
            "conditions_cleared": ["frightened"],
        }
    )
    assert "Long rest" in long
    assert "frightened" in long


def test_progress_status_text_cycles_ellipsis() -> None:
    assert progress_status_text("The DM considers your move", 0).endswith(".")
    assert progress_status_text("The DM considers your move", 1).endswith("..")
    assert progress_status_text("The DM considers your move", 2).endswith("...")
    assert progress_status_text("The DM considers your move", 3).endswith(".")


def test_format_stream_event_hides_raw_tool_calls() -> None:
    assert (
        format_stream_event(
            {
                "type": "tool_call",
                "tool_name": "skill_check",
                "args": {"skill": "perception", "dc": 12},
            }
        )
        is None
    )


def test_format_stream_event_progress_is_status_only() -> None:
    assert (
        format_stream_event(
            {
                "type": "progress",
                "phase": "awaiting_dm",
                "label": "The DM considers your move",
            }
        )
        is None
    )


def test_format_latest_turn_labels_player_and_dm() -> None:
    text = format_latest_turn(
        LatestTurn(
            turn_number=2,
            player_text="I listen at the crack.",
            narration="Whispers echo from deeper in.",
            status="ok",
        )
    )
    assert "Latest Turn 2" in text
    assert "I listen at the crack." in text
    assert "Whispers echo from deeper in." in text


def test_format_stream_roll_is_dramatic_and_permanent() -> None:
    text = format_stream_event(
        {
            "type": "roll",
            "event": {
                "type": "skill_check_resolved",
                "skill": "perception",
                "d20": 17,
                "modifier": 3,
                "total": 20,
                "dc": 12,
                "success": True,
            },
        }
    )
    assert text is not None
    assert "Perception" in text or "perception" in text
    assert "SUCCESS" in text
    assert "20" in text
    assert "12" in text
