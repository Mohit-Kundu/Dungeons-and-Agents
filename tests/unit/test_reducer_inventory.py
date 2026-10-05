"""Seam: Reducer applies ItemTaken / ItemConsumed Events."""

from __future__ import annotations

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.events import ItemConsumed, ItemTaken, SessionCreated
from dnd_agent.domain.models import AbilityScores, Character, Item, Quest
from dnd_agent.store.reducer import apply_event, fold_events


def _created_at_den() -> SessionCreated:
    scenario = load_scenario("goblin_cave")
    return SessionCreated(
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
            inventory=[
                Item(id="longsword", name="Longsword", qty=1),
                Item(id="ration", name="Rations (1 day)", qty=5, consumable=True),
            ],
        ),
        location="goblin_den",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Drive goblins out.",
            status="active",
        ),
        rng_seed=10,
        world=scenario.build_world(current_location_id="goblin_den"),
    )


def test_item_taken_moves_location_stack_into_inventory() -> None:
    created = _created_at_den()
    state = apply_event(None, created)
    event = ItemTaken(
        item_id="stolen_goods",
        name="Stolen Village Goods",
        qty=1,
        from_location_id="goblin_den",
        reason="recover loot",
    )
    next_state = apply_event(state, event)

    den = next(loc for loc in next_state.world.locations if loc.id == "goblin_den")
    assert not any(item.id == "stolen_goods" for item in den.items)
    assert any(
        item.id == "stolen_goods" and item.qty == 1 for item in next_state.character.inventory
    )
    assert fold_events([created, event]) == next_state


def test_item_taken_preserves_consumable_flag_from_event() -> None:
    created = _created_at_den()
    world = created.world.model_copy(
        update={
            "locations": [
                loc.model_copy(
                    update={
                        "items": [
                            Item(
                                id="trail_ration",
                                name="Trail Ration",
                                qty=1,
                                consumable=True,
                            )
                        ]
                    }
                )
                if loc.id == "goblin_den"
                else loc
                for loc in created.world.locations
            ]
        }
    )
    created_with_stack = created.model_copy(update={"world": world})
    event = ItemTaken(
        item_id="trail_ration",
        name="Trail Ration",
        qty=1,
        from_location_id="goblin_den",
        consumable=True,
        reason="pocket snack",
    )
    next_state = apply_event(apply_event(None, created_with_stack), event)
    taken = next(item for item in next_state.character.inventory if item.id == "trail_ration")
    assert taken.consumable is True
    assert fold_events([created_with_stack, event]) == next_state


def test_item_consumed_reduces_qty_and_removes_zero_stacks() -> None:
    created = _created_at_den()
    state = apply_event(None, created)

    after_one = apply_event(
        state,
        ItemConsumed(
            item_id="ration",
            qty=1,
            source="inventory",
            reason="eat",
        ),
    )
    ration = next(item for item in after_one.character.inventory if item.id == "ration")
    assert ration.qty == 4

    # drain remaining 4
    drained = after_one
    for _ in range(4):
        drained = apply_event(
            drained,
            ItemConsumed(item_id="ration", qty=1, source="inventory", reason="eat"),
        )
    assert not any(item.id == "ration" for item in drained.character.inventory)
