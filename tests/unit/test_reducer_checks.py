"""Seam: Reducer applies skill-check and location Events."""

from __future__ import annotations

from dnd_agent.domain.events import LocationChanged, SessionCreated, SkillCheckResolved
from dnd_agent.domain.models import AbilityScores, Character, Item, Quest
from dnd_agent.store.reducer import apply_event, fold_events


def _created() -> SessionCreated:
    return SessionCreated(
        session_id="sess_1",
        scenario_id="goblin_cave",
        character=Character(
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
            proficient_skills=["perception"],
            max_hp=12,
            hp=12,
            hit_die=10,
            hit_dice_total=1,
            hit_dice_remaining=1,
            armor_class=16,
            inventory=[Item(id="longsword", name="Longsword", qty=1)],
            conditions=[],
        ),
        location="Cave Mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive goblins out.",
            status="active",
        ),
        rng_seed=10,
    )


def test_skill_check_event_advances_rng_seed() -> None:
    state = apply_event(None, _created())
    event = SkillCheckResolved(
        skill="perception",
        ability="wisdom",
        dc=12,
        expression="1d20",
        rolls=[15],
        d20=15,
        modifier=0,
        total=15,
        success=True,
        reason="search",
        next_rng_seed=99,
    )
    next_state = apply_event(state, event)
    assert next_state.rng_seed == 99
    assert fold_events([_created(), event]).rng_seed == 99


def test_location_changed_updates_location() -> None:
    state = apply_event(None, _created())
    next_state = apply_event(
        state,
        LocationChanged(location="Goblin Den", reason="crept inside"),
    )
    assert next_state.location == "Goblin Den"
