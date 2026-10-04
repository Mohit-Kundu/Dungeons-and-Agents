"""Pure rules engine: dice, checks, saves, conditions, and rests."""

from dnd_agent.rules.checks import CheckResult, skill_check
from dnd_agent.rules.conditions import KNOWN_CONDITIONS, effects_for, normalize_condition
from dnd_agent.rules.dice import DiceRng, RollResult, d20_expression, parse_dice, roll
from dnd_agent.rules.rests import LongRestResult, ShortRestResult, long_rest, short_rest
from dnd_agent.rules.saves import SaveResult, saving_throw

__all__ = [
    "KNOWN_CONDITIONS",
    "CheckResult",
    "DiceRng",
    "LongRestResult",
    "RollResult",
    "SaveResult",
    "ShortRestResult",
    "d20_expression",
    "effects_for",
    "long_rest",
    "normalize_condition",
    "parse_dice",
    "roll",
    "saving_throw",
    "short_rest",
    "skill_check",
]
