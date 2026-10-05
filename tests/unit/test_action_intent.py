"""Seam: Action Intent validation against Playable Facts."""

from __future__ import annotations

from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.models import (
    AbilityScores,
    Character,
    GameState,
    Item,
    Quest,
)
from dnd_agent.world.intent import (
    ProposedActionIntent,
    validate_action_intent,
)


def _state(*, location_id: str = "cave_mouth", inventory: list[Item] | None = None) -> GameState:
    scenario = load_scenario("goblin_cave")
    return GameState(
        session_id="sess_intent",
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
            inventory=inventory or [Item(id="longsword", name="Longsword", qty=1)],
        ),
        location=location_id,
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Clear it.",
            status="active",
        ),
        rng_seed=1,
        world=scenario.build_world(current_location_id=location_id),
    )


def test_valid_use_of_inventory_item() -> None:
    result = validate_action_intent(
        _state(),
        ProposedActionIntent(kind="use", item_ids=["longsword"], confidence="high"),
    )
    assert result.ok
    assert result.intent is not None
    assert result.intent.kind == "use"
    assert result.intent.item_ids == ["longsword"]


def test_valid_interact_at_current_location() -> None:
    result = validate_action_intent(
        _state(location_id="cave_mouth"),
        ProposedActionIntent(
            kind="interact",
            interactable_ids=["muddy_tracks"],
            confidence="high",
        ),
    )
    assert result.ok
    assert result.intent is not None
    assert result.intent.interactable_ids == ["muddy_tracks"]


def test_valid_travel_to_reachable_destination() -> None:
    result = validate_action_intent(
        _state(location_id="cave_mouth"),
        ProposedActionIntent(
            kind="travel",
            destination_id="twisting_tunnel",
            confidence="high",
        ),
    )
    assert result.ok
    assert result.intent is not None
    assert result.intent.destination_id == "twisting_tunnel"


def test_rejects_missing_item() -> None:
    result = validate_action_intent(
        _state(),
        ProposedActionIntent(kind="use", item_ids=["vorpal_blade"], confidence="high"),
    )
    assert not result.ok
    assert "unknown" in result.reason.lower() or "unavailable" in result.reason.lower()


def test_rejects_remote_interactable() -> None:
    result = validate_action_intent(
        _state(location_id="cave_mouth"),
        ProposedActionIntent(
            kind="interact",
            interactable_ids=["war_drum"],
            confidence="high",
        ),
    )
    assert not result.ok
    assert "unavailable" in result.reason.lower() or "not present" in result.reason.lower()


def test_valid_resolve_enemy_at_current_location() -> None:
    result = validate_action_intent(
        _state(location_id="goblin_den"),
        ProposedActionIntent(
            kind="resolve_enemy",
            enemy_group_ids=["den_goblins"],
            confidence="high",
        ),
    )
    assert result.ok
    assert result.intent is not None
    assert result.intent.enemy_group_ids == ["den_goblins"]


def test_rejects_remote_enemy_group() -> None:
    result = validate_action_intent(
        _state(location_id="cave_mouth"),
        ProposedActionIntent(
            kind="resolve_enemy",
            enemy_group_ids=["den_goblins"],
            confidence="high",
        ),
    )
    assert not result.ok
    assert "unavailable" in result.reason.lower() or "not present" in result.reason.lower()


def test_rejects_unreachable_travel() -> None:
    result = validate_action_intent(
        _state(location_id="cave_mouth"),
        ProposedActionIntent(
            kind="travel",
            destination_id="goblin_den",
            confidence="high",
        ),
    )
    assert not result.ok
    assert "no route" in result.reason.lower()


def test_rejects_ambiguous_intent() -> None:
    result = validate_action_intent(
        _state(),
        ProposedActionIntent(
            kind="use",
            item_ids=["longsword", "shield"],
            confidence="high",
            ambiguous=True,
        ),
    )
    assert not result.ok
    assert "ambiguous" in result.reason.lower()


def test_rejects_low_confidence_intent() -> None:
    result = validate_action_intent(
        _state(),
        ProposedActionIntent(kind="general", confidence="low"),
    )
    assert not result.ok
    assert "uncertain" in result.reason.lower() or "confidence" in result.reason.lower()


def test_valid_general_action_has_no_targets() -> None:
    result = validate_action_intent(
        _state(),
        ProposedActionIntent(kind="general", confidence="high"),
    )
    assert result.ok
    assert result.intent is not None
    assert result.intent.kind == "general"
