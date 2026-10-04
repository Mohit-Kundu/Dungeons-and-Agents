"""Pure rules engine: dice, checks, and later saves/conditions/rests."""

from dnd_agent.rules.checks import CheckResult, skill_check
from dnd_agent.rules.dice import DiceRng, RollResult, parse_dice, roll

__all__ = [
    "CheckResult",
    "DiceRng",
    "RollResult",
    "parse_dice",
    "roll",
    "skill_check",
]
