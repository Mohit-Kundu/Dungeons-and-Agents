"""Seam: pure inventory take / use / consume against PlayableWorld."""

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
from dnd_agent.world.inventory import plan_consume, plan_take, plan_use


def _state_at(
    location_id: str,
    *,
    inventory: list[Item] | None = None,
) -> GameState:
    scenario = load_scenario("goblin_cave")
    world = scenario.build_world(current_location_id=location_id)
    return GameState(
        session_id="sess_inv",
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
            inventory=inventory
            if inventory is not None
            else [
                Item(id="longsword", name="Longsword", qty=1),
                Item(id="ration", name="Rations (1 day)", qty=5, consumable=True),
            ],
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


def test_plan_take_transfers_portable_location_item() -> None:
    plan = plan_take(_state_at("goblin_den"), "stolen_goods")
    assert plan.item_id == "stolen_goods"
    assert plan.name == "Stolen Village Goods"
    assert plan.qty == 1
    assert plan.from_location_id == "goblin_den"


def test_plan_take_rejects_non_portable_remote_and_unavailable() -> None:
    den = _state_at("goblin_den")
    mouth = _state_at("cave_mouth")

    with pytest.raises(ValueError, match="non-portable"):
        plan_take(den, "war_drum")
    with pytest.raises(ValueError, match="remote"):
        plan_take(mouth, "stolen_goods")
    with pytest.raises(ValueError, match="unavailable"):
        plan_take(den, "longsword")
    with pytest.raises(ValueError, match="unknown"):
        plan_take(den, "magic_boots")


def test_plan_use_accepts_inventory_and_nearby_location_item() -> None:
    den = _state_at("goblin_den")
    inventory_plan = plan_use(den, "ration")
    assert inventory_plan.source == "inventory"
    assert inventory_plan.consumable is True
    assert inventory_plan.qty == 5

    location_plan = plan_use(den, "stolen_goods")
    assert location_plan.source == "location"
    assert location_plan.location_id == "goblin_den"
    assert location_plan.consumable is False


def test_plan_use_rejects_remote_and_unknown() -> None:
    mouth = _state_at("cave_mouth")
    with pytest.raises(ValueError, match="remote"):
        plan_use(mouth, "stolen_goods")
    with pytest.raises(ValueError, match="unknown"):
        plan_use(mouth, "magic_boots")


def test_plan_consume_deducts_without_underflow_and_tracks_zero_remaining() -> None:
    state = _state_at(
        "cave_mouth",
        inventory=[Item(id="ration", name="Rations (1 day)", qty=2, consumable=True)],
    )
    first = plan_consume(state, "ration")
    assert first.qty == 1
    assert first.qty_remaining == 1
    assert first.source == "inventory"

    last = plan_consume(
        _state_at(
            "cave_mouth",
            inventory=[Item(id="ration", name="Rations (1 day)", qty=1, consumable=True)],
        ),
        "ration",
    )
    assert last.qty_remaining == 0

    with pytest.raises(ValueError, match="exhausted"):
        plan_consume(
            _state_at(
                "cave_mouth",
                inventory=[Item(id="ration", name="Rations (1 day)", qty=1, consumable=True)],
            ),
            "ration",
            qty=2,
        )
    with pytest.raises(ValueError, match="not consumable"):
        plan_consume(_state_at("cave_mouth"), "longsword")
