"""Ability and skill checks."""

from __future__ import annotations

from dataclasses import dataclass

from dnd_agent.domain.models import AbilityScores, Character
from dnd_agent.rules.dice import DiceRng, roll

SKILL_ABILITIES: dict[str, str] = {
    "athletics": "strength",
    "acrobatics": "dexterity",
    "sleight_of_hand": "dexterity",
    "stealth": "dexterity",
    "arcana": "intelligence",
    "history": "intelligence",
    "investigation": "intelligence",
    "nature": "intelligence",
    "religion": "intelligence",
    "animal_handling": "wisdom",
    "insight": "wisdom",
    "medicine": "wisdom",
    "perception": "wisdom",
    "survival": "wisdom",
    "deception": "charisma",
    "intimidation": "charisma",
    "performance": "charisma",
    "persuasion": "charisma",
}


def ability_modifier(scores: AbilityScores, ability: str) -> int:
    score = getattr(scores, ability)
    return (score - 10) // 2


@dataclass(frozen=True)
class CheckResult:
    skill: str
    ability: str
    dc: int
    expression: str
    rolls: list[int]
    d20: int
    modifier: int
    total: int
    success: bool
    reason: str


def skill_check(
    character: Character,
    *,
    skill: str,
    dc: int,
    rng: DiceRng,
    advantage: bool = False,
    disadvantage: bool = False,
    reason: str = "",
) -> CheckResult:
    key = skill.strip().lower().replace(" ", "_")
    if key not in SKILL_ABILITIES:
        raise ValueError(f"unknown skill: {skill}")
    if advantage and disadvantage:
        advantage = False
        disadvantage = False

    ability = SKILL_ABILITIES[key]
    modifier = ability_modifier(character.abilities, ability)
    if key in {s.lower().replace(" ", "_") for s in character.proficient_skills}:
        modifier += character.proficiency_bonus

    if advantage:
        expression = "2d20kh1"
    elif disadvantage:
        expression = "2d20kl1"
    else:
        expression = "1d20"

    rolled = roll(expression, rng)
    d20 = rolled.total  # expression has no mod; kept die sum
    total = d20 + modifier
    return CheckResult(
        skill=key,
        ability=ability,
        dc=dc,
        expression=rolled.expression,
        rolls=list(rolled.rolls),
        d20=d20,
        modifier=modifier,
        total=total,
        success=total >= dc,
        reason=reason,
    )
