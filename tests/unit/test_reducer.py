"""Seam: Reducer applies Events to GameState."""

from __future__ import annotations

from dnd_agent.domain.events import SessionCreated
from dnd_agent.domain.models import (
    AbilityScores,
    Character,
    GameState,
    Item,
    Quest,
)
from dnd_agent.store.reducer import apply_event, fold_events


def _starter_character() -> Character:
    return Character(
        id="pregen_fighter",
        name="Brynn Ironfoot",
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
        proficient_skills=["athletics", "intimidation"],
        max_hp=12,
        hp=12,
        hit_die=10,
        hit_dice_total=1,
        hit_dice_remaining=1,
        armor_class=16,
        inventory=[Item(id="longsword", name="Longsword", qty=1)],
        conditions=[],
    )


def test_session_created_builds_initial_game_state() -> None:
    character = _starter_character()
    event = SessionCreated(
        session_id="sess_1",
        scenario_id="goblin_cave",
        character=character,
        location="Cave Mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive the goblins out of the cave.",
            status="active",
        ),
        rng_seed=42,
    )

    state = apply_event(None, event)

    assert state.session_id == "sess_1"
    assert state.scenario_id == "goblin_cave"
    assert state.location == "Cave Mouth"
    assert state.character.name == "Brynn Ironfoot"
    assert state.character.hp == 12
    assert state.character.inventory[0].id == "longsword"
    assert state.quest.title == "Clear the Cave"
    assert state.rng_seed == 42
    assert state.summary == ""


def test_fold_events_replays_to_same_state_as_last_apply() -> None:
    character = _starter_character()
    created = SessionCreated(
        session_id="sess_2",
        scenario_id="goblin_cave",
        character=character,
        location="Cave Mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive the goblins out of the cave.",
            status="active",
        ),
        rng_seed=7,
    )

    folded = fold_events([created])
    stepped = apply_event(None, created)

    assert folded == stepped
    assert isinstance(folded, GameState)
