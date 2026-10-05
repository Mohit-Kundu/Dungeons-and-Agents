"""Seam: CLI consume_turn_stream clears waits around permanent reveals."""

from __future__ import annotations

from dnd_agent.cli.main import consume_turn_stream
from dnd_agent.domain.models import AbilityScores, Character, GameState, Quest


class FakeProgress:
    def __init__(self) -> None:
        self.labels: list[str] = []
        self.clears = 0
        self.pulses = 0
        self.active = False

    def show(self, label: str) -> None:
        self.active = True
        self.labels.append(label)

    def pulse(self) -> None:
        self.pulses += 1

    def clear(self) -> None:
        self.clears += 1
        self.active = False


def _done_state() -> dict:
    character = Character(
        id="c1",
        name="Brynn",
        level=1,
        class_name="fighter",
        abilities=AbilityScores(
            strength=16,
            dexterity=12,
            constitution=14,
            intelligence=10,
            wisdom=12,
            charisma=8,
        ),
        proficiency_bonus=2,
        max_hp=12,
        hp=12,
        hit_die=10,
        hit_dice_total=1,
        hit_dice_remaining=1,
        armor_class=16,
    )
    state = GameState(
        session_id="sess_test",
        scenario_id="goblin_cave",
        character=character,
        location="Cave Mouth",
        quest=Quest(id="q", title="Scout", summary="Look around"),
        rng_seed=1,
    )
    return state.model_dump(mode="json")


def test_consume_turn_stream_keeps_spinner_until_roll_then_narration() -> None:
    progress = FakeProgress()
    events = [
        {"type": "progress", "phase": "awaiting_dm", "label": "The DM considers your move"},
        {
            "type": "progress",
            "phase": "rolling",
            "label": "Dice tumble for perception (DC 12)...",
        },
        {
            "type": "tool_call",
            "tool_name": "skill_check",
            "args": {"skill": "perception", "dc": 12},
        },
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
        },
        {"type": "progress", "phase": "awaiting_dm", "label": "The DM weaves the outcome"},
        {"type": "narration_delta", "text": "Tracks lead deeper."},
        {
            "type": "done",
            "turn_number": 1,
            "status": "ok",
            "state": _done_state(),
            "narration": "Tracks lead deeper.",
        },
    ]

    state = consume_turn_stream(iter(events), progress=progress)

    assert state is not None
    assert state.session_id == "sess_test"
    assert progress.labels[0] == "The DM considers your move"
    assert any("perception" in label.lower() for label in progress.labels)
    assert any("weaves" in label.lower() for label in progress.labels)
    assert progress.pulses >= 1
    assert progress.clears >= 2
    assert progress.active is False
