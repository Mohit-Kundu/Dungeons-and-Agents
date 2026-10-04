"""Seam: conditions modify Checks and Saves per defined rules."""

from __future__ import annotations

import pytest

from dnd_agent.domain.models import AbilityScores, Character, Item
from dnd_agent.rules.checks import skill_check
from dnd_agent.rules.conditions import KNOWN_CONDITIONS, normalize_condition
from dnd_agent.rules.dice import DiceRng
from dnd_agent.rules.saves import saving_throw


def _fighter(*, conditions: list[str] | None = None, hp: int = 12) -> Character:
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
        hp=hp,
        hit_die=10,
        hit_dice_total=1,
        hit_dice_remaining=1,
        armor_class=16,
        inventory=[Item(id="longsword", name="Longsword", qty=1)],
        conditions=list(conditions or []),
    )


def test_known_conditions_cover_poc_set() -> None:
    assert frozenset(
        {"poisoned", "frightened", "restrained", "blinded", "prone"}
    ) == KNOWN_CONDITIONS


def test_normalize_condition_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown condition"):
        normalize_condition("on_fire")


def test_poisoned_imposes_disadvantage_on_skill_check() -> None:
    result = skill_check(
        _fighter(conditions=["poisoned"]),
        skill="athletics",
        dc=10,
        rng=DiceRng(seed=1),
    )
    assert result.expression == "2d20kl1"


def test_frightened_cancels_explicit_advantage_on_check() -> None:
    result = skill_check(
        _fighter(conditions=["frightened"]),
        skill="perception",
        dc=10,
        rng=DiceRng(seed=2),
        advantage=True,
    )
    assert result.expression == "1d20"


def test_blinded_auto_fails_perception() -> None:
    result = skill_check(
        _fighter(conditions=["blinded"]),
        skill="perception",
        dc=5,
        rng=DiceRng(seed=3),
    )
    assert result.success is False
    assert result.expression == "auto_fail"
    assert result.d20 == 0
    assert result.rolls == []


def test_restrained_imposes_disadvantage_on_dexterity_save() -> None:
    result = saving_throw(
        _fighter(conditions=["restrained"]),
        ability="dexterity",
        dc=12,
        rng=DiceRng(seed=4),
    )
    assert result.expression == "2d20kl1"


def test_restrained_does_not_affect_constitution_save() -> None:
    result = saving_throw(
        _fighter(conditions=["restrained"]),
        ability="constitution",
        dc=12,
        rng=DiceRng(seed=5),
    )
    assert result.expression == "1d20"
