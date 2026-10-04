"""Named Conditions and their mechanical effects on Checks/Saves."""

from __future__ import annotations

from dataclasses import dataclass

KNOWN_CONDITIONS: frozenset[str] = frozenset(
    {"poisoned", "frightened", "restrained", "blinded", "prone"}
)


@dataclass(frozen=True)
class ConditionEffects:
    """Aggregated Check/Save modifiers from a character's Conditions."""

    check_disadvantage: bool = False
    auto_fail_skills: frozenset[str] = frozenset()
    save_disadvantage_abilities: frozenset[str] = frozenset()


def _condition_key(condition: str) -> str:
    return condition.strip().lower().replace(" ", "_")


def normalize_condition(condition: str) -> str:
    key = _condition_key(condition)
    if key not in KNOWN_CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")
    return key


def effects_for(conditions: list[str]) -> ConditionEffects:
    check_disadvantage = False
    auto_fail: set[str] = set()
    save_disadvantage: set[str] = set()

    for raw in conditions:
        key = _condition_key(raw)
        if key not in KNOWN_CONDITIONS:
            continue
        if key in {"poisoned", "frightened"}:
            check_disadvantage = True
        elif key == "restrained":
            save_disadvantage.add("dexterity")
        elif key == "blinded":
            # POC: treat Perception as sight-based (D-014).
            auto_fail.add("perception")
        elif key == "prone":
            # Tracked for state/rest clearing; attack effects come later.
            pass

    return ConditionEffects(
        check_disadvantage=check_disadvantage,
        auto_fail_skills=frozenset(auto_fail),
        save_disadvantage_abilities=frozenset(save_disadvantage),
    )
