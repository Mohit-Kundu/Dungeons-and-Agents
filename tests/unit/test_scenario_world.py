"""Seam: Scenario content declares and validates authoritative Playable Facts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd_agent.content.loader import Scenario, load_scenario


def _valid_scenario(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "test_cave",
        "title": "Test Cave",
        "starting_location": "cave_mouth",
        "character_id": "pregen_fighter",
        "quest": {
            "id": "clear_cave",
            "title": "Clear the Cave",
            "summary": "Clear it.",
            "status": "active",
        },
        "locations": [
            {
                "id": "cave_mouth",
                "name": "Cave Mouth",
                "description": "Entrance",
                "exits": ["goblin_den"],
                "interactables": [
                    {"id": "muddy_tracks", "name": "Muddy Tracks"},
                ],
                "items": [],
            },
            {
                "id": "goblin_den",
                "name": "Goblin Den",
                "description": "Den",
                "exits": ["cave_mouth"],
                "interactables": [],
                "items": [
                    {"id": "stolen_goods", "name": "Stolen Goods", "qty": 1},
                ],
            },
        ],
        "enemy_groups": [
            {
                "id": "den_goblins",
                "name": "Goblin Raiders",
                "location_id": "goblin_den",
                "count": 3,
                "hp_per_enemy": 7,
                "resolution_damage": 7,
            }
        ],
        "objectives": [
            {
                "id": "reach_den",
                "title": "Reach the den",
                "predicate": {
                    "type": "location_visited",
                    "location_id": "goblin_den",
                },
            },
            {
                "id": "defeat_goblins",
                "title": "Defeat the goblins",
                "predicate": {
                    "type": "enemies_defeated",
                    "enemy_group_id": "den_goblins",
                },
            },
            {
                "id": "recover_goods",
                "title": "Recover goods",
                "predicate": {
                    "type": "inventory_contains",
                    "item_id": "stolen_goods",
                },
            },
        ],
    }
    data.update(overrides)
    return data


def test_goblin_cave_declares_authoritative_playable_world() -> None:
    scenario = load_scenario("goblin_cave")

    location_ids = {location.id for location in scenario.locations}
    assert scenario.starting_location == "cave_mouth"
    assert location_ids == {"cave_mouth", "twisting_tunnel", "goblin_den"}

    mouth = next(loc for loc in scenario.locations if loc.id == "cave_mouth")
    assert "twisting_tunnel" in mouth.exits
    assert any(item.id == "stolen_goods" for loc in scenario.locations for item in loc.items)

    assert len(scenario.enemy_groups) >= 1
    goblins = scenario.enemy_groups[0]
    assert goblins.count >= 1
    assert goblins.hp_per_enemy >= 1
    assert goblins.resolution_damage >= 1
    assert goblins.location_id in location_ids

    predicate_types = {objective.predicate.type for objective in scenario.objectives}
    assert predicate_types == {
        "location_visited",
        "enemies_defeated",
        "inventory_contains",
    }


def test_valid_scenario_accepts_playable_world() -> None:
    scenario = Scenario.model_validate(_valid_scenario())
    assert scenario.starting_location == "cave_mouth"
    assert len(scenario.objectives) == 3


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        (
            {
                "locations": [
                    {
                        "id": "cave_mouth",
                        "name": "Cave Mouth",
                        "exits": [],
                        "interactables": [],
                        "items": [],
                    },
                    {
                        "id": "cave_mouth",
                        "name": "Duplicate",
                        "exits": [],
                        "interactables": [],
                        "items": [],
                    },
                ]
            },
            "duplicate location id",
        ),
        (
            {
                "locations": [
                    {
                        "id": "cave_mouth",
                        "name": "Cave Mouth",
                        "exits": ["goblin_den"],
                        "interactables": [],
                        "items": [],
                    },
                    {
                        "id": "goblin_den",
                        "name": "Goblin Den",
                        "exits": ["cave_mouth"],
                        "interactables": [
                            {"id": "muddy_tracks", "name": "Tracks A"},
                            {"id": "muddy_tracks", "name": "Tracks B"},
                        ],
                        "items": [{"id": "stolen_goods", "name": "Stolen Goods", "qty": 1}],
                    },
                ]
            },
            "duplicate interactable id",
        ),
        (
            {
                "locations": [
                    {
                        "id": "cave_mouth",
                        "name": "Cave Mouth",
                        "exits": ["goblin_den"],
                        "interactables": [],
                        "items": [{"id": "stolen_goods", "name": "Goods A", "qty": 1}],
                    },
                    {
                        "id": "goblin_den",
                        "name": "Goblin Den",
                        "exits": ["cave_mouth"],
                        "interactables": [],
                        "items": [{"id": "stolen_goods", "name": "Goods B", "qty": 1}],
                    },
                ]
            },
            "duplicate item id",
        ),
        (
            {
                "locations": [
                    {
                        "id": "cave_mouth",
                        "name": "Cave Mouth",
                        "exits": ["missing_room"],
                        "interactables": [],
                        "items": [],
                    }
                ]
            },
            "unknown exit",
        ),
        ({"starting_location": "missing_room"}, "starting location"),
        (
            {
                "enemy_groups": [
                    {
                        "id": "den_goblins",
                        "name": "Goblin Raiders",
                        "location_id": "goblin_den",
                        "count": 0,
                        "hp_per_enemy": 7,
                        "resolution_damage": 7,
                    }
                ]
            },
            "greater than or equal to 1",
        ),
        (
            {
                "enemy_groups": [
                    {
                        "id": "den_goblins",
                        "name": "Goblin Raiders",
                        "location_id": "missing_room",
                        "count": 3,
                        "hp_per_enemy": 7,
                        "resolution_damage": 7,
                    }
                ]
            },
            "enemy group location",
        ),
        (
            {
                "objectives": [
                    {
                        "id": "bad",
                        "title": "Bad",
                        "predicate": {
                            "type": "location_visited",
                            "location_id": "missing_room",
                        },
                    }
                ]
            },
            "objective location",
        ),
        (
            {
                "objectives": [
                    {
                        "id": "bad",
                        "title": "Bad",
                        "predicate": {
                            "type": "enemies_defeated",
                            "enemy_group_id": "missing_group",
                        },
                    }
                ]
            },
            "objective enemy group",
        ),
        (
            {
                "objectives": [
                    {
                        "id": "bad",
                        "title": "Bad",
                        "predicate": {
                            "type": "inventory_contains",
                            "item_id": "missing_item",
                        },
                    }
                ]
            },
            "objective item",
        ),
    ],
)
def test_scenario_rejects_invalid_playable_references(
    overrides: dict[str, object],
    fragment: str,
) -> None:
    with pytest.raises(ValidationError, match=fragment):
        Scenario.model_validate(_valid_scenario(**overrides))
