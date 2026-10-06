"""Dice expression parsing and seeded rolls."""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

_DICE_RE = re.compile(
    r"^(?P<count>\d+)d(?P<sides>\d+)"
    r"(?:(?P<kh>kh)(?P<kh_n>\d+)|(?P<kl>kl)(?P<kl_n>\d+))?"
    r"(?P<mod>[+-]\d+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DiceExpression:
    count: int
    sides: int
    modifier: int = 0
    keep_highest: int | None = None
    keep_lowest: int | None = None

    def __str__(self) -> str:
        base = f"{self.count}d{self.sides}"
        if self.keep_highest is not None:
            base += f"kh{self.keep_highest}"
        if self.keep_lowest is not None:
            base += f"kl{self.keep_lowest}"
        if self.modifier:
            base += f"{self.modifier:+d}"
        return base


@dataclass(frozen=True)
class RollResult:
    expression: str
    rolls: list[int]
    kept: list[int]
    modifier: int
    total: int


class RngSource(Protocol):
    """Minimal dice RNG surface. Seeded implementations advance via `next_seed()`."""

    seed: int

    def randint(self, lo: int, hi: int) -> int: ...

    def next_seed(self) -> int: ...


RngFactory = Callable[[int], RngSource]


class DiceRng:
    """Seeded RNG. After rolls, call `next_seed()` and persist that on GameState."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._rng = random.Random(seed)

    def randint(self, lo: int, hi: int) -> int:
        return self._rng.randint(lo, hi)

    def next_seed(self) -> int:
        return self._rng.randint(0, 2**31 - 1)


def d20_expression(*, advantage: bool = False, disadvantage: bool = False) -> str:
    """Resolve advantage/disadvantage into a d20 dice expression (they cancel)."""
    if advantage and disadvantage:
        return "1d20"
    if advantage:
        return "2d20kh1"
    if disadvantage:
        return "2d20kl1"
    return "1d20"


def parse_dice(expression: str) -> DiceExpression:
    cleaned = expression.strip().lower().replace(" ", "")
    match = _DICE_RE.fullmatch(cleaned)
    if match is None:
        raise ValueError(f"invalid dice expression: {expression}")

    count = int(match.group("count"))
    sides = int(match.group("sides"))
    if count < 1 or sides < 2:
        raise ValueError(f"invalid dice expression: {expression}")

    modifier = int(match.group("mod") or 0)
    keep_highest = int(match.group("kh_n")) if match.group("kh") else None
    keep_lowest = int(match.group("kl_n")) if match.group("kl") else None
    if keep_highest is not None and keep_lowest is not None:
        raise ValueError("cannot keep highest and lowest together")
    if keep_highest is not None and not 1 <= keep_highest <= count:
        raise ValueError("keep highest out of range")
    if keep_lowest is not None and not 1 <= keep_lowest <= count:
        raise ValueError("keep lowest out of range")

    return DiceExpression(
        count=count,
        sides=sides,
        modifier=modifier,
        keep_highest=keep_highest,
        keep_lowest=keep_lowest,
    )


def roll(expression: str, rng: RngSource) -> RollResult:
    parsed = parse_dice(expression)
    rolls = [rng.randint(1, parsed.sides) for _ in range(parsed.count)]
    kept = list(rolls)
    if parsed.keep_highest is not None:
        kept = sorted(rolls, reverse=True)[: parsed.keep_highest]
    elif parsed.keep_lowest is not None:
        kept = sorted(rolls)[: parsed.keep_lowest]
    total = sum(kept) + parsed.modifier
    return RollResult(
        expression=str(parsed),
        rolls=rolls,
        kept=kept,
        modifier=parsed.modifier,
        total=total,
    )
