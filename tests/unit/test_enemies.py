"""Seam: plan_resolve_enemy applies Scenario damage from Turn Check evidence."""

from __future__ import annotations

import pytest

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.events import EnemyGroupDamaged, SkillCheckResolved
from dnd_agent.domain.models import AbilityScores, Character, GameState, Item, Quest
from dnd_agent.world.enemies import plan_resolve_enemy
from dnd_agent.world.intent import available_enemy_group_ids


def _state_at(location_id: str, *, current_hp: int | None = None) -> GameState:
    scenario = load_scenario("goblin_cave")
    world = scenario.build_world(current_location_id=location_id)
    if current_hp is not None:
        world = world.model_copy(
            update={
                "enemy_groups": [
                    group.model_copy(update={"current_hp": current_hp})
                    if group.id == "den_goblins"
                    else group
                    for group in world.enemy_groups
                ]
            }
        )
    return GameState(
        session_id="sess_enemy",
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
        location=location_id,
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive goblins out.",
            status="active",
        ),
        rng_seed=1,
        world=world,
    )


def _success_check() -> SkillCheckResolved:
    return SkillCheckResolved(
        skill="athletics",
        ability="strength",
        dc=10,
        expression="1d20",
        rolls=[15],
        d20=15,
        modifier=5,
        total=20,
        success=True,
        reason="strike",
        next_rng_seed=2,
    )


def _failed_check() -> SkillCheckResolved:
    return SkillCheckResolved(
        skill="athletics",
        ability="strength",
        dc=25,
        expression="1d20",
        rolls=[2],
        d20=2,
        modifier=5,
        total=7,
        success=False,
        reason="miss",
        next_rng_seed=2,
    )


def test_successful_check_applies_resolution_damage_and_derives_counts() -> None:
    state = _state_at("goblin_den")
    plan = plan_resolve_enemy(state, "den_goblins", turn_events=[_success_check()])

    assert plan.enemy_group_id == "den_goblins"
    assert plan.damage == 7
    assert plan.current_hp == 14  # 21 - 7
    assert plan.max_hp == 21
    assert plan.remaining_count == 2
    assert plan.defeated_count == 1


def test_failed_check_rejects_without_plan() -> None:
    state = _state_at("goblin_den")
    with pytest.raises(ValueError, match="successful qualifying Check"):
        plan_resolve_enemy(state, "den_goblins", turn_events=[_failed_check()])


def test_damage_clamps_at_zero_and_defeats_last_enemy() -> None:
    state = _state_at("goblin_den", current_hp=5)
    plan = plan_resolve_enemy(state, "den_goblins", turn_events=[_success_check()])

    assert plan.damage == 5
    assert plan.current_hp == 0
    assert plan.remaining_count == 0
    assert plan.defeated_count == 3

    defeated = _state_at("goblin_den", current_hp=0)
    assert "den_goblins" not in available_enemy_group_ids(defeated)


def test_remaining_count_threshold_crosses_on_partial_hp() -> None:
    # 8 HP left with 7 HP/enemy → still one enemy; 7 damage drops to 1 HP → still one.
    state = _state_at("goblin_den", current_hp=8)
    plan = plan_resolve_enemy(state, "den_goblins", turn_events=[_success_check()])
    assert plan.current_hp == 1
    assert plan.remaining_count == 1
    assert plan.defeated_count == 2


def test_rejects_remote_unknown_and_defeated_targets() -> None:
    remote = _state_at("cave_mouth")
    with pytest.raises(ValueError, match="not present"):
        plan_resolve_enemy(remote, "den_goblins", turn_events=[_success_check()])

    present = _state_at("goblin_den")
    with pytest.raises(ValueError, match="unknown"):
        plan_resolve_enemy(present, "missing_horde", turn_events=[_success_check()])

    defeated = _state_at("goblin_den", current_hp=0)
    with pytest.raises(ValueError, match="defeated"):
        plan_resolve_enemy(defeated, "den_goblins", turn_events=[_success_check()])


def test_one_successful_check_cannot_fund_two_resolutions() -> None:
    state = _state_at("goblin_den")
    check = _success_check()
    plan = plan_resolve_enemy(state, "den_goblins", turn_events=[check])
    prior = EnemyGroupDamaged(
        enemy_group_id=plan.enemy_group_id,
        damage=plan.damage,
        current_hp=plan.current_hp,
        reason="first hit",
    )
    with pytest.raises(ValueError, match="successful qualifying Check"):
        plan_resolve_enemy(state, "den_goblins", turn_events=[check, prior])
