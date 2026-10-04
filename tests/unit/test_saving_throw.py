"""Seam: saving throws use ability modifiers + dice + DC."""

from __future__ import annotations

from dnd_agent.domain.models import AbilityScores, Character, Item
from dnd_agent.rules.dice import DiceRng
from dnd_agent.rules.saves import saving_throw


def _fighter() -> Character:
    return Character(
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
        proficient_skills=["athletics", "perception"],
        max_hp=12,
        hp=12,
        hit_die=10,
        hit_dice_total=1,
        hit_dice_remaining=1,
        armor_class=16,
        inventory=[Item(id="longsword", name="Longsword", qty=1)],
        conditions=[],
    )


def test_saving_throw_uses_ability_modifier() -> None:
    # CON 14 → +2
    result = saving_throw(
        _fighter(),
        ability="constitution",
        dc=13,
        rng=DiceRng(seed=0),
    )
    assert result.ability == "constitution"
    assert result.modifier == 2
    assert result.total == result.d20 + 2
    assert result.success == (result.total >= 13)
    assert result.expression == "1d20"


def test_saving_throw_rejects_unknown_ability() -> None:
    try:
        saving_throw(
            _fighter(),
            ability="luck",
            dc=10,
            rng=DiceRng(seed=1),
        )
    except ValueError as exc:
        assert "unknown ability" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")
