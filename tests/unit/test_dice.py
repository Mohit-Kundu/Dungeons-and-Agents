"""Seam: dice parser and seeded rolls."""

from __future__ import annotations

from dnd_agent.rules.dice import DiceRng, parse_dice, roll


def test_parse_simple_dice() -> None:
    expr = parse_dice("2d6+3")
    assert expr.count == 2
    assert expr.sides == 6
    assert expr.modifier == 3
    assert expr.keep_highest is None
    assert expr.keep_lowest is None


def test_parse_advantage_and_disadvantage() -> None:
    adv = parse_dice("2d20kh1")
    dis = parse_dice("2d20kl1")
    assert adv.keep_highest == 1
    assert dis.keep_lowest == 1


def test_seeded_roll_is_deterministic() -> None:
    first = roll("1d20", DiceRng(seed=123))
    second = roll("1d20", DiceRng(seed=123))
    assert first.rolls == second.rolls
    assert first.total == second.total
    assert 1 <= first.total <= 20


def test_advantage_keeps_higher_die() -> None:
    rng = DiceRng(seed=1)
    result = roll("2d20kh1", rng)
    assert len(result.rolls) == 2
    assert result.total == max(result.rolls)
