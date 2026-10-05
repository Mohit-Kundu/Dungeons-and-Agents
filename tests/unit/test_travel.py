"""Seam: travel validation and reachable destinations from PlayableWorld."""

from __future__ import annotations

import pytest

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.models import (
    AbilityScores,
    Character,
    GameState,
    Item,
    Quest,
)
from dnd_agent.world.travel import (
    reachable_destinations,
    resolve_location_ref,
    validate_travel,
)


def _state_at(location_id: str) -> GameState:
    scenario = load_scenario("goblin_cave")
    world = scenario.build_world(current_location_id=location_id)
    return GameState(
        session_id="sess_travel",
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
            max_hp=12,
            hp=12,
            hit_die=10,
            hit_dice_total=1,
            hit_dice_remaining=1,
            armor_class=16,
            inventory=[Item(id="longsword", name="Longsword", qty=1)],
        ),
        location=location_id,
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Clear it.",
            status="active",
        ),
        rng_seed=1,
        world=world,
    )


def test_reachable_destinations_from_cave_mouth() -> None:
    destinations = reachable_destinations(_state_at("cave_mouth"))
    assert [dest.id for dest in destinations] == ["twisting_tunnel"]
    assert destinations[0].name == "Twisting Tunnel"


def test_reachable_destinations_branch_from_twisting_tunnel() -> None:
    destinations = reachable_destinations(_state_at("twisting_tunnel"))
    assert {dest.id for dest in destinations} == {"cave_mouth", "goblin_den"}


def test_validate_travel_accepts_adjacent_exit() -> None:
    assert validate_travel(_state_at("cave_mouth"), "twisting_tunnel") == "twisting_tunnel"
    assert validate_travel(_state_at("cave_mouth"), "Twisting Tunnel") == "twisting_tunnel"


def test_validate_travel_rejects_unknown_current_and_unreachable() -> None:
    state = _state_at("cave_mouth")
    with pytest.raises(ValueError, match="unknown"):
        validate_travel(state, "moon_base")
    with pytest.raises(ValueError, match="already"):
        validate_travel(state, "cave_mouth")
    with pytest.raises(ValueError, match="no route"):
        validate_travel(state, "goblin_den")


def test_resolve_location_ref_maps_name_or_id() -> None:
    world = _state_at("cave_mouth").world
    assert resolve_location_ref(world, "goblin_den") == "goblin_den"
    assert resolve_location_ref(world, "Goblin Den") == "goblin_den"
    assert resolve_location_ref(world, "nowhere") is None
