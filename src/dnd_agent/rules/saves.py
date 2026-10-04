"""Saving throws."""

from __future__ import annotations

from dataclasses import dataclass

from dnd_agent.domain.models import Character
from dnd_agent.rules.checks import ability_modifier
from dnd_agent.rules.conditions import effects_for
from dnd_agent.rules.dice import DiceRng, d20_expression, roll

ABILITIES: frozenset[str] = frozenset(
    {"strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"}
)


@dataclass(frozen=True)
class SaveResult:
    ability: str
    dc: int
    expression: str
    rolls: list[int]
    d20: int
    modifier: int
    total: int
    success: bool
    reason: str


def saving_throw(
    character: Character,
    *,
    ability: str,
    dc: int,
    rng: DiceRng,
    advantage: bool = False,
    disadvantage: bool = False,
    reason: str = "",
) -> SaveResult:
    key = ability.strip().lower()
    if key not in ABILITIES:
        raise ValueError(f"unknown ability: {ability}")

    modifier = ability_modifier(character.abilities, key)
    effects = effects_for(character.conditions)
    if key in effects.save_disadvantage_abilities:
        disadvantage = True
    expression = d20_expression(advantage=advantage, disadvantage=disadvantage)

    rolled = roll(expression, rng)
    d20 = rolled.total
    total = d20 + modifier
    return SaveResult(
        ability=key,
        dc=dc,
        expression=rolled.expression,
        rolls=list(rolled.rolls),
        d20=d20,
        modifier=modifier,
        total=total,
        success=total >= dc,
        reason=reason,
    )
