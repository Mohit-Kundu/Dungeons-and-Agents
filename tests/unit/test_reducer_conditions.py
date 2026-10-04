"""Seam: Reducer applies condition, save, and rest Events."""

from __future__ import annotations

from dnd_agent.domain.events import (
    ConditionAdded,
    ConditionRemoved,
    LongRestCompleted,
    SavingThrowResolved,
    SessionCreated,
    ShortRestCompleted,
)
from dnd_agent.domain.models import AbilityScores, Character, Item, Quest
from dnd_agent.store.reducer import apply_event


def _created(*, hp: int = 12, conditions: list[str] | None = None) -> SessionCreated:
    return SessionCreated(
        session_id="sess_1",
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
            proficient_skills=["perception"],
            max_hp=12,
            hp=hp,
            hit_die=10,
            hit_dice_total=1,
            hit_dice_remaining=1,
            armor_class=16,
            inventory=[Item(id="longsword", name="Longsword", qty=1)],
            conditions=list(conditions or []),
        ),
        location="Cave Mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive goblins out.",
            status="active",
        ),
        rng_seed=10,
    )


def test_condition_added_and_removed() -> None:
    state = apply_event(None, _created())
    with_poison = apply_event(state, ConditionAdded(condition="poisoned", reason="gas"))
    assert with_poison.character.conditions == ["poisoned"]
    cleared = apply_event(
        with_poison, ConditionRemoved(condition="poisoned", reason="antidote")
    )
    assert cleared.character.conditions == []


def test_saving_throw_advances_rng_seed() -> None:
    state = apply_event(None, _created())
    next_state = apply_event(
        state,
        SavingThrowResolved(
            ability="constitution",
            dc=13,
            expression="1d20",
            rolls=[12],
            d20=12,
            modifier=2,
            total=14,
            success=True,
            reason="poison",
            next_rng_seed=77,
        ),
    )
    assert next_state.rng_seed == 77


def test_short_rest_updates_hp_and_hit_dice() -> None:
    state = apply_event(None, _created(hp=4))
    next_state = apply_event(
        state,
        ShortRestCompleted(
            hit_dice_spent=1,
            hit_dice_rolls=[8],
            hp_recovered=10,
            hp_after=12,
            hit_dice_remaining=0,
            reason="camp",
            next_rng_seed=55,
        ),
    )
    assert next_state.character.hp == 12
    assert next_state.character.hit_dice_remaining == 0
    assert next_state.rng_seed == 55


def test_long_rest_clears_conditions_and_restores() -> None:
    state = apply_event(None, _created(hp=4, conditions=["poisoned"]))
    next_state = apply_event(
        state,
        LongRestCompleted(
            hp_after=12,
            hit_dice_restored=1,
            hit_dice_remaining=1,
            conditions_cleared=["poisoned"],
            reason="night",
        ),
    )
    assert next_state.character.hp == 12
    assert next_state.character.hit_dice_remaining == 1
    assert next_state.character.conditions == []
