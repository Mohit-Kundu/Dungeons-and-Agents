"""Seam: CLI formats condition/save/rest Events for display."""

from __future__ import annotations

from dnd_agent.cli.render import format_turn_event


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
    assert "Save" in text
    assert "constitution" in text
    assert "success" in text


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
