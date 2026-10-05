"""Seam: objective predicates evaluate against authoritative GameState."""

from __future__ import annotations

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.models import AbilityScores, Character, GameState, Item, Quest
from dnd_agent.world.objectives import (
    incomplete_objectives,
    plan_progress_events,
    predicate_satisfied,
)


def _state(
    *,
    location: str = "cave_mouth",
    visited: list[str] | None = None,
    inventory: list[Item] | None = None,
    enemy_hp: int | None = None,
) -> GameState:
    scenario = load_scenario("goblin_cave")
    world = scenario.build_world(current_location_id=location)
    if visited is not None:
        world = world.model_copy(update={"visited_location_ids": list(visited)})
    if enemy_hp is not None:
        world = world.model_copy(
            update={
                "enemy_groups": [
                    group.model_copy(update={"current_hp": enemy_hp})
                    if group.id == "den_goblins"
                    else group
                    for group in world.enemy_groups
                ]
            }
        )
    return GameState(
        session_id="sess_obj",
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
            inventory=inventory
            or [Item(id="longsword", name="Longsword", qty=1)],
        ),
        location=location,
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive goblins out.",
            status="active",
        ),
        rng_seed=1,
        world=world,
    )


def test_location_visited_predicate() -> None:
    state = _state(location="goblin_den", visited=["cave_mouth", "goblin_den"])
    objective = next(o for o in state.world.objectives if o.id == "reach_goblin_den")
    assert predicate_satisfied(state, objective.predicate) is True

    start = _state()
    start_obj = next(o for o in start.world.objectives if o.id == "reach_goblin_den")
    assert predicate_satisfied(start, start_obj.predicate) is False


def test_inventory_contains_predicate() -> None:
    empty = _state()
    objective = next(o for o in empty.world.objectives if o.id == "recover_stolen_goods")
    assert predicate_satisfied(empty, objective.predicate) is False

    carrying = _state(
        inventory=[
            Item(id="longsword", name="Longsword", qty=1),
            Item(id="stolen_goods", name="Stolen Village Goods", qty=1),
        ]
    )
    assert predicate_satisfied(carrying, objective.predicate) is True


def test_enemies_defeated_predicate() -> None:
    alive = _state(location="goblin_den")
    objective = next(o for o in alive.world.objectives if o.id == "defeat_den_goblins")
    assert predicate_satisfied(alive, objective.predicate) is False

    dead = _state(location="goblin_den", enemy_hp=0)
    assert predicate_satisfied(dead, objective.predicate) is True


def test_plan_progress_emits_objective_then_quest_exactly_once() -> None:
    state = _state(
        location="goblin_den",
        visited=["cave_mouth", "twisting_tunnel", "goblin_den"],
        inventory=[
            Item(id="longsword", name="Longsword", qty=1),
            Item(id="stolen_goods", name="Stolen Village Goods", qty=1),
        ],
        enemy_hp=0,
    )
    events = plan_progress_events(state)
    assert [event.type for event in events] == [
        "objective_completed",
        "objective_completed",
        "objective_completed",
        "quest_completed",
    ]
    assert {event.objective_id for event in events if event.type == "objective_completed"} == {
        "reach_goblin_den",
        "defeat_den_goblins",
        "recover_stolen_goods",
    }
    assert events[-1].quest_id == "clear_cave"

    # After applying statuses, repeated planning is empty (idempotent).
    completed_world = state.world.model_copy(
        update={
            "objectives": [
                objective.model_copy(update={"status": "completed"})
                for objective in state.world.objectives
            ]
        }
    )
    completed = state.model_copy(
        update={
            "world": completed_world,
            "quest": state.quest.model_copy(update={"status": "completed"}),
        }
    )
    assert plan_progress_events(completed) == []


def test_incomplete_objectives_lists_only_active() -> None:
    state = _state()
    incomplete = incomplete_objectives(state)
    assert [item.id for item in incomplete] == [
        "reach_goblin_den",
        "defeat_den_goblins",
        "recover_stolen_goods",
    ]

    world = state.world.model_copy(
        update={
            "objectives": [
                objective.model_copy(update={"status": "completed"})
                if objective.id == "reach_goblin_den"
                else objective
                for objective in state.world.objectives
            ]
        }
    )
    partial = state.model_copy(update={"world": world})
    assert [item.id for item in incomplete_objectives(partial)] == [
        "defeat_den_goblins",
        "recover_stolen_goods",
    ]
