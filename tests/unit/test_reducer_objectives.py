"""Seam: Reducer applies ObjectiveCompleted / QuestCompleted exactly once."""

from __future__ import annotations

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.events import ObjectiveCompleted, QuestCompleted, SessionCreated
from dnd_agent.domain.models import AbilityScores, Character, Item, Quest
from dnd_agent.store.reducer import apply_event, fold_events
from dnd_agent.world.objectives import plan_progress_events


def _created() -> SessionCreated:
    scenario = load_scenario("goblin_cave")
    return SessionCreated(
        session_id="sess_obj_reducer",
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
        rng_seed=10,
        world=scenario.build_world(current_location_id="cave_mouth"),
    )


def test_objective_completed_marks_status_once() -> None:
    created = _created()
    state = apply_event(None, created)
    event = ObjectiveCompleted(
        objective_id="reach_goblin_den",
        title="Reach the Goblin Den",
        reason="predicate_satisfied",
    )
    next_state = apply_event(state, event)
    objective = next(o for o in next_state.world.objectives if o.id == "reach_goblin_den")
    assert objective.status == "completed"
    assert apply_event(next_state, event) == next_state
    assert fold_events([created, event]) == next_state


def test_quest_completed_marks_quest_once() -> None:
    created = _created()
    state = apply_event(None, created)
    for objective in state.world.objectives:
        state = apply_event(
            state,
            ObjectiveCompleted(
                objective_id=objective.id,
                title=objective.title,
                reason="setup",
            ),
        )
    quest_event = QuestCompleted(
        quest_id="clear_cave",
        title="Clear the Cave",
        reason="all_objectives_complete",
    )
    done = apply_event(state, quest_event)
    assert done.quest.status == "completed"
    assert apply_event(done, quest_event) == done


def test_plan_then_fold_completes_quest_from_satisfied_state() -> None:
    created = _created()
    world = created.world.model_copy(
        update={
            "visited_location_ids": ["cave_mouth", "goblin_den"],
            "enemy_groups": [
                group.model_copy(update={"current_hp": 0})
                if group.id == "den_goblins"
                else group
                for group in created.world.enemy_groups
            ],
        }
    )
    character = created.character.model_copy(
        update={
            "inventory": [
                *created.character.inventory,
                Item(id="stolen_goods", name="Stolen Village Goods", qty=1),
            ]
        }
    )
    created_ready = created.model_copy(
        update={"world": world, "character": character, "location": "goblin_den"}
    )
    state = apply_event(None, created_ready)
    progress = plan_progress_events(state)
    folded = fold_events([created_ready, *progress])
    assert all(o.status == "completed" for o in folded.world.objectives)
    assert folded.quest.status == "completed"
    assert plan_progress_events(folded) == []
