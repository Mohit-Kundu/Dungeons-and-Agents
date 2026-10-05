"""Seam: CLI renders incomplete objectives and enemy status."""

from __future__ import annotations

from dnd_agent.cli.render import (
    format_enemy_statuses,
    format_incomplete_objectives,
    format_turn_event,
    render_state,
)
from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.models import AbilityScores, Character, GameState, Item, Quest
from dnd_agent.world.enemies import EnemyStatus
from dnd_agent.world.objectives import IncompleteObjective


def _state() -> GameState:
    scenario = load_scenario("goblin_cave")
    return GameState(
        session_id="sess_cli_obj",
        scenario_id="goblin_cave",
        character=Character(
            id="pregen_fighter",
            name="Brynn",
            level=1,
            class_name="Fighter",
            abilities=AbilityScores(
                strength=16,
                dexterity=12,
                constitution=14,
                intelligence=10,
                wisdom=11,
                charisma=13,
            ),
            proficiency_bonus=2,
            max_hp=12,
            hp=12,
            hit_die=10,
            hit_dice_total=1,
            hit_dice_remaining=1,
            armor_class=16,
            inventory=[Item(id="longsword", name="Longsword", qty=1)],
        ),
        location="cave_mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive goblins out.",
            status="active",
        ),
        rng_seed=1,
        world=scenario.build_world(current_location_id="cave_mouth"),
    )


def test_format_incomplete_objectives() -> None:
    text = format_incomplete_objectives(
        [IncompleteObjective(id="reach_goblin_den", title="Reach the Goblin Den")]
    )
    assert "Reach the Goblin Den" in text
    assert "reach_goblin_den" in text


def test_format_enemy_statuses() -> None:
    text = format_enemy_statuses(
        [
            EnemyStatus(
                id="den_goblins",
                name="Goblin Raiders",
                location_id="goblin_den",
                current_hp=14,
                max_hp=21,
                remaining_count=2,
                defeated_count=1,
            )
        ]
    )
    assert "Goblin Raiders" in text
    assert "HP 14/21" in text
    assert "2 left" in text


def test_format_objective_and_quest_events() -> None:
    assert "Objective" in format_turn_event(
        {"type": "objective_completed", "objective_id": "x", "title": "Reach"}
    )
    assert "Quest" in format_turn_event(
        {"type": "quest_completed", "quest_id": "clear_cave", "title": "Clear the Cave"}
    )


def test_render_state_includes_objectives_and_enemies() -> None:
    # Smoke: should not raise; includes objective and enemy rows via helpers.
    render_state(_state())
