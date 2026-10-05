"""Seam: Reducer applies EnemyGroupDamaged and rebuilds remaining counts."""

from __future__ import annotations

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.events import EnemyGroupDamaged, SessionCreated
from dnd_agent.domain.models import AbilityScores, Character, Item, Quest
from dnd_agent.store.reducer import apply_event, fold_events
from dnd_agent.world.intent import available_enemy_group_ids


def _created_at_den() -> SessionCreated:
    scenario = load_scenario("goblin_cave")
    return SessionCreated(
        session_id="sess_enemy_reducer",
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
        location="goblin_den",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive goblins out.",
            status="active",
        ),
        rng_seed=10,
        world=scenario.build_world(current_location_id="goblin_den"),
    )


def test_enemy_group_damaged_updates_hp_and_derived_counts() -> None:
    created = _created_at_den()
    state = apply_event(None, created)
    event = EnemyGroupDamaged(
        enemy_group_id="den_goblins",
        damage=7,
        current_hp=14,
        reason="strike",
    )
    next_state = apply_event(state, event)
    goblins = next(g for g in next_state.world.enemy_groups if g.id == "den_goblins")

    assert goblins.current_hp == 14
    assert goblins.max_hp == 21
    assert goblins.remaining_count == 2
    assert goblins.defeated_count == 1
    assert fold_events([created, event]) == next_state


def test_repeated_damage_replay_defeats_group_without_underflow() -> None:
    created = _created_at_den()
    hits = [
        EnemyGroupDamaged(enemy_group_id="den_goblins", damage=7, current_hp=14, reason="1"),
        EnemyGroupDamaged(enemy_group_id="den_goblins", damage=7, current_hp=7, reason="2"),
        EnemyGroupDamaged(enemy_group_id="den_goblins", damage=7, current_hp=0, reason="3"),
    ]
    state = fold_events([created, *hits])
    goblins = next(g for g in state.world.enemy_groups if g.id == "den_goblins")

    assert goblins.current_hp == 0
    assert goblins.remaining_count == 0
    assert goblins.defeated_count == 3
    assert "den_goblins" not in available_enemy_group_ids(state)
