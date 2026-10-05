"""Deterministic inventory take / use / consume against Playable Facts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from dnd_agent.domain.models import GameState, Item, WorldLocation


class TakePlan(BaseModel):
    item_id: str
    name: str
    qty: int = Field(ge=1)
    from_location_id: str
    consumable: bool = False


class UsePlan(BaseModel):
    item_id: str
    name: str
    qty: int = Field(ge=1)
    source: Literal["inventory", "location"]
    location_id: str | None = None
    consumable: bool = False


class ConsumePlan(BaseModel):
    item_id: str
    name: str
    qty: int = Field(ge=1)
    qty_remaining: int = Field(ge=0)
    source: Literal["inventory", "location"]
    location_id: str | None = None


def _current_location(state: GameState) -> WorldLocation | None:
    for location in state.world.locations:
        if location.id == state.location:
            return location
    return None


def _known_item_ids(state: GameState) -> set[str]:
    ids = {item.id for item in state.character.inventory}
    for location in state.world.locations:
        ids.update(item.id for item in location.items)
    return ids


def _known_interactable_ids(state: GameState) -> set[str]:
    return {
        interactable.id
        for location in state.world.locations
        for interactable in location.interactables
    }


def plan_take(state: GameState, item_id: str) -> TakePlan:
    """Plan transferring a portable nearby Item into inventory."""
    text = item_id.strip()
    if not text:
        raise ValueError("item_id must not be empty")

    if text in _known_interactable_ids(state):
        raise ValueError(f"non-portable item: {text}")

    current = _current_location(state)
    if current is None:
        raise ValueError(f"unknown current location: {state.location}")

    for item in current.items:
        if item.id == text:
            return TakePlan(
                item_id=item.id,
                name=item.name,
                qty=item.qty,
                from_location_id=current.id,
                consumable=item.consumable,
            )

    known = _known_item_ids(state)
    if text not in known:
        raise ValueError(f"unknown item: {text}")

    for location in state.world.locations:
        if any(item.id == text for item in location.items):
            raise ValueError(f"remote item: {text}")

    raise ValueError(f"unavailable item: {text}")


def plan_use(state: GameState, item_id: str) -> UsePlan:
    """Validate that an Item is available to use from inventory or surroundings."""
    text = item_id.strip()
    if not text:
        raise ValueError("item_id must not be empty")

    if text in _known_interactable_ids(state):
        raise ValueError(f"non-portable item: {text}")

    for item in state.character.inventory:
        if item.id == text:
            return UsePlan(
                item_id=item.id,
                name=item.name,
                qty=item.qty,
                source="inventory",
                consumable=item.consumable,
            )

    current = _current_location(state)
    if current is not None:
        for item in current.items:
            if item.id == text:
                return UsePlan(
                    item_id=item.id,
                    name=item.name,
                    qty=item.qty,
                    source="location",
                    location_id=current.id,
                    consumable=item.consumable,
                )

    known = _known_item_ids(state)
    if text not in known:
        raise ValueError(f"unknown item: {text}")

    for location in state.world.locations:
        if any(item.id == text for item in location.items):
            raise ValueError(f"remote item: {text}")

    raise ValueError(f"unavailable item: {text}")


def plan_consume(state: GameState, item_id: str, qty: int = 1) -> ConsumePlan:
    """Plan deterministic consumable quantity deduction without underflow."""
    if qty < 1:
        raise ValueError("qty must be at least 1")

    use = plan_use(state, item_id)
    if not use.consumable:
        raise ValueError(f"item is not consumable: {use.item_id}")
    if use.qty < qty:
        raise ValueError(f"exhausted item: {use.item_id}")

    return ConsumePlan(
        item_id=use.item_id,
        name=use.name,
        qty=qty,
        qty_remaining=use.qty - qty,
        source=use.source,
        location_id=use.location_id,
    )
