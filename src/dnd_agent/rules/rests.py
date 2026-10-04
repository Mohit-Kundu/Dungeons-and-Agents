"""Short and long rests."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from dnd_agent.domain.models import Character
from dnd_agent.rules.checks import ability_modifier
from dnd_agent.rules.dice import DiceRng, roll


@dataclass(frozen=True)
class ShortRestResult:
    hit_dice_spent: int
    hit_dice_rolls: list[int]
    hp_recovered: int
    hp_after: int
    hit_dice_remaining: int
    reason: str


@dataclass(frozen=True)
class LongRestResult:
    hp_after: int
    hit_dice_restored: int
    hit_dice_remaining: int
    conditions_cleared: list[str]
    reason: str


def short_rest(
    character: Character,
    *,
    hit_dice_to_spend: int,
    rng: DiceRng,
    reason: str = "",
) -> ShortRestResult:
    if hit_dice_to_spend < 1:
        raise ValueError("must spend at least 1 hit die")
    if hit_dice_to_spend > character.hit_dice_remaining:
        raise ValueError(
            f"not enough hit dice: have {character.hit_dice_remaining}, "
            f"tried to spend {hit_dice_to_spend}"
        )

    con_mod = ability_modifier(character.abilities, "constitution")
    rolls: list[int] = []
    recovered = 0
    expression = f"1d{character.hit_die}"
    for _ in range(hit_dice_to_spend):
        rolled = roll(expression, rng)
        rolls.append(rolled.total)
        recovered += max(0, rolled.total + con_mod)

    hp_after = min(character.max_hp, character.hp + recovered)
    actual_recovered = hp_after - character.hp
    return ShortRestResult(
        hit_dice_spent=hit_dice_to_spend,
        hit_dice_rolls=rolls,
        hp_recovered=actual_recovered,
        hp_after=hp_after,
        hit_dice_remaining=character.hit_dice_remaining - hit_dice_to_spend,
        reason=reason,
    )


def long_rest(character: Character, *, reason: str = "") -> LongRestResult:
    regain = ceil(character.hit_dice_total / 2)
    spent = character.hit_dice_total - character.hit_dice_remaining
    restored = min(regain, spent)
    remaining = character.hit_dice_remaining + restored
    cleared = list(character.conditions)
    return LongRestResult(
        hp_after=character.max_hp,
        hit_dice_restored=restored,
        hit_dice_remaining=remaining,
        conditions_cleared=cleared,
        reason=reason,
    )
