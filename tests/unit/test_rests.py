"""Seam: short/long rests update HP, hit dice, and conditions."""

from __future__ import annotations

import pytest

from dnd_agent.domain.models import AbilityScores, Character, Item
from dnd_agent.rules.dice import DiceRng
from dnd_agent.rules.rests import long_rest, short_rest


def _fighter(
    *,
    hp: int = 4,
    hit_dice_total: int = 4,
    hit_dice_remaining: int = 3,
    conditions: list[str] | None = None,
) -> Character:
    return Character(
        id="pregen_fighter",
        name="Brynn",
        level=4,
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
        proficient_skills=["athletics"],
        max_hp=36,
        hp=hp,
        hit_die=10,
        hit_dice_total=hit_dice_total,
        hit_dice_remaining=hit_dice_remaining,
        armor_class=16,
        inventory=[Item(id="longsword", name="Longsword", qty=1)],
        conditions=list(conditions or []),
    )


def test_short_rest_spends_hit_dice_and_heals() -> None:
    # CON +2; seeded d10 roll is deterministic
    result = short_rest(
        _fighter(hp=4, hit_dice_remaining=3),
        hit_dice_to_spend=1,
        rng=DiceRng(seed=0),
    )
    assert result.hit_dice_spent == 1
    assert len(result.hit_dice_rolls) == 1
    assert 1 <= result.hit_dice_rolls[0] <= 10
    assert result.hp_recovered == result.hit_dice_rolls[0] + 2
    assert result.hp_after == min(36, 4 + result.hp_recovered)
    assert result.hit_dice_remaining == 2


def test_short_rest_rejects_spending_more_than_remaining() -> None:
    with pytest.raises(ValueError, match="hit dice"):
        short_rest(
            _fighter(hit_dice_remaining=1),
            hit_dice_to_spend=2,
            rng=DiceRng(seed=1),
        )


def test_long_rest_restores_hp_hit_dice_and_clears_conditions() -> None:
    # total 4 → regain ceil(4/2)=2; remaining was 1 so after = min(4, 1+2)=3
    result = long_rest(
        _fighter(
            hp=4,
            hit_dice_total=4,
            hit_dice_remaining=1,
            conditions=["poisoned", "frightened"],
        )
    )
    assert result.hp_after == 36
    assert result.hit_dice_restored == 2
    assert result.hit_dice_remaining == 3
    assert result.conditions_cleared == ["poisoned", "frightened"]
