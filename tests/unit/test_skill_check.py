"""Seam: skill checks use sheet modifiers + dice + DC."""

from __future__ import annotations

from dnd_agent.domain.models import AbilityScores, Character, Item
from dnd_agent.rules.checks import skill_check
from dnd_agent.rules.dice import DiceRng


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
        hit_dice_total=1,
        hit_dice_remaining=1,
        armor_class=16,
        inventory=[Item(id="longsword", name="Longsword", qty=1)],
        conditions=[],
    )


def test_skill_check_includes_ability_and_proficiency() -> None:
    # STR 16 → +3, proficient athletics → +2, total mod +5
    result = skill_check(
        _fighter(),
        skill="athletics",
        dc=10,
        rng=DiceRng(seed=0),
    )
    assert result.modifier == 5
    assert result.total == result.d20 + 5
    assert result.success == (result.total >= 10)
    assert result.skill == "athletics"
    assert result.ability == "strength"


def test_skill_check_advantage_uses_kh_expression() -> None:
    result = skill_check(
        _fighter(),
        skill="perception",
        dc=15,
        rng=DiceRng(seed=2),
        advantage=True,
    )
    assert result.expression == "2d20kh1"
    assert len(result.rolls) == 2
