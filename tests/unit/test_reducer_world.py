"""Seam: Reducer seeds and replays PlayableWorld from SessionCreated."""

from __future__ import annotations

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.events import SessionCreated
from dnd_agent.domain.models import AbilityScores, Character, GameState, Item, Quest
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


def test_session_created_seeds_playable_world_and_survives_fold() -> None:
    scenario = load_scenario("goblin_cave")
    world = scenario.build_world(current_location_id="cave_mouth")
    event = SessionCreated(
        session_id="sess_world",
        scenario_id="goblin_cave",
        character=_starter_character(),
        location="cave_mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive the goblins out of the cave.",
            status="active",
        ),
        rng_seed=42,
        world=world,
    )

    state = apply_event(None, event)
    folded = fold_events([event])

    assert state.world.is_seeded()
    assert state.location == "cave_mouth"
    assert state.world.visited_location_ids == ["cave_mouth"]
    assert {location.id for location in state.world.locations} == {
        "cave_mouth",
        "twisting_tunnel",
        "goblin_den",
    }
    goblins = next(group for group in state.world.enemy_groups if group.id == "den_goblins")
    assert goblins.current_hp == goblins.count * goblins.hp_per_enemy
    assert goblins.remaining_count == goblins.count
    assert len(state.world.objectives) == 3
    assert folded == state
    assert isinstance(folded, GameState)


def test_legacy_session_created_without_world_defaults_empty() -> None:
    event = SessionCreated(
        session_id="sess_legacy",
        scenario_id="goblin_cave",
        character=_starter_character(),
        location="Cave Mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive the goblins out of the cave.",
            status="active",
        ),
        rng_seed=7,
    )

    state = apply_event(None, event)

    assert not state.world.is_seeded()
    assert state.location == "Cave Mouth"
