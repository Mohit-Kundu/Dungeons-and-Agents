"""Pure Reducer: Events → GameState."""

from __future__ import annotations

from collections.abc import Callable

from dnd_agent.domain.events import (
    ConditionAdded,
    ConditionRemoved,
    DiceRolled,
    EnemyGroupDamaged,
    Event,
    ItemConsumed,
    ItemTaken,
    LocationChanged,
    LongRestCompleted,
    ObjectiveCompleted,
    QuestCompleted,
    SavingThrowResolved,
    SessionCreated,
    ShortRestCompleted,
    SkillCheckResolved,
    SummaryUpdated,
)
from dnd_agent.domain.models import (
    Character,
    EnemyGroup,
    GameState,
    Item,
    Objective,
    PlayableWorld,
    WorldLocation,
)


def _with_character(state: GameState, character: Character, **updates: object) -> GameState:
    return state.model_copy(update={"character": character, **updates})


def _add_inventory_stack(
    inventory: list[Item],
    item_id: str,
    name: str,
    qty: int,
    *,
    consumable: bool = False,
) -> list[Item]:
    next_inventory: list[Item] = []
    merged = False
    for item in inventory:
        if item.id == item_id:
            next_inventory.append(
                item.model_copy(
                    update={
                        "qty": item.qty + qty,
                        "name": name,
                        "consumable": consumable,
                    }
                )
            )
            merged = True
        else:
            next_inventory.append(item)
    if not merged:
        next_inventory.append(
            Item(id=item_id, name=name, qty=qty, consumable=consumable)
        )
    return next_inventory


def _deduct_stack(items: list[Item], item_id: str, qty: int) -> list[Item]:
    next_items: list[Item] = []
    found = False
    for item in items:
        if item.id != item_id:
            next_items.append(item)
            continue
        found = True
        remaining = item.qty - qty
        if remaining < 0:
            raise ValueError(f"cannot underflow item stack: {item_id}")
        if remaining > 0:
            next_items.append(item.model_copy(update={"qty": remaining}))
    if not found:
        raise ValueError(f"item stack not present: {item_id}")
    return next_items


def _replace_location(
    world: PlayableWorld,
    location_id: str,
    updater: Callable[[WorldLocation], WorldLocation],
) -> PlayableWorld:
    locations: list[WorldLocation] = []
    found = False
    for location in world.locations:
        if location.id == location_id:
            locations.append(updater(location))
            found = True
        else:
            locations.append(location)
    if not found:
        raise ValueError(f"unknown location: {location_id}")
    return world.model_copy(update={"locations": locations})


def _replace_enemy_group(
    world: PlayableWorld,
    enemy_group_id: str,
    updater: Callable[[EnemyGroup], EnemyGroup],
) -> PlayableWorld:
    groups: list[EnemyGroup] = []
    found = False
    for group in world.enemy_groups:
        if group.id == enemy_group_id:
            groups.append(updater(group))
            found = True
        else:
            groups.append(group)
    if not found:
        raise KeyError(f"unknown enemy group: {enemy_group_id}")
    return world.model_copy(update={"enemy_groups": groups})


def _replace_objective(
    world: PlayableWorld,
    objective_id: str,
    updater: Callable[[Objective], Objective],
) -> PlayableWorld:
    objectives: list[Objective] = []
    found = False
    for objective in world.objectives:
        if objective.id == objective_id:
            objectives.append(updater(objective))
            found = True
        else:
            objectives.append(objective)
    if not found:
        raise KeyError(f"unknown objective: {objective_id}")
    return world.model_copy(update={"objectives": objectives})


def apply_event(state: GameState | None, event: Event) -> GameState:
    """Apply one Event. `state` is None only before SessionCreated."""
    if isinstance(event, SessionCreated):
        if state is not None:
            raise ValueError("SessionCreated can only start an empty Session")
        return GameState(
            session_id=event.session_id,
            scenario_id=event.scenario_id,
            character=event.character.model_copy(deep=True),
            location=event.location,
            quest=event.quest.model_copy(deep=True),
            rng_seed=event.rng_seed,
            summary=event.summary,
            world=event.world.model_copy(deep=True),
        )

    if state is None:
        raise ValueError(f"{type(event).__name__} requires an existing GameState")

    if isinstance(event, DiceRolled):
        return state.model_copy(update={"rng_seed": event.next_rng_seed})

    if isinstance(event, SkillCheckResolved):
        return state.model_copy(update={"rng_seed": event.next_rng_seed})

    if isinstance(event, SavingThrowResolved):
        return state.model_copy(update={"rng_seed": event.next_rng_seed})

    if isinstance(event, ConditionAdded):
        if event.condition in state.character.conditions:
            return state
        conditions = [*state.character.conditions, event.condition]
        return _with_character(state, state.character.model_copy(update={"conditions": conditions}))

    if isinstance(event, ConditionRemoved):
        conditions = [c for c in state.character.conditions if c != event.condition]
        return _with_character(state, state.character.model_copy(update={"conditions": conditions}))

    if isinstance(event, ShortRestCompleted):
        character = state.character.model_copy(
            update={
                "hp": event.hp_after,
                "hit_dice_remaining": event.hit_dice_remaining,
            }
        )
        return _with_character(state, character, rng_seed=event.next_rng_seed)

    if isinstance(event, LongRestCompleted):
        character = state.character.model_copy(
            update={
                "hp": event.hp_after,
                "hit_dice_remaining": event.hit_dice_remaining,
                "conditions": [],
            }
        )
        return _with_character(state, character)

    if isinstance(event, LocationChanged):
        visited = list(state.world.visited_location_ids)
        if event.location not in visited:
            visited.append(event.location)
        world = state.world.model_copy(update={"visited_location_ids": visited})
        return state.model_copy(update={"location": event.location, "world": world})

    if isinstance(event, ItemTaken):
        def _take_from_location(location: WorldLocation) -> WorldLocation:
            return location.model_copy(
                update={"items": _deduct_stack(location.items, event.item_id, event.qty)}
            )

        world = _replace_location(state.world, event.from_location_id, _take_from_location)
        inventory = _add_inventory_stack(
            state.character.inventory,
            event.item_id,
            event.name,
            event.qty,
            consumable=event.consumable,
        )
        character = state.character.model_copy(update={"inventory": inventory})
        return _with_character(state, character, world=world)

    if isinstance(event, ItemConsumed):
        if event.source == "inventory":
            inventory = _deduct_stack(state.character.inventory, event.item_id, event.qty)
            character = state.character.model_copy(update={"inventory": inventory})
            return _with_character(state, character)

        if event.location_id is None:
            raise ValueError("location ItemConsumed requires location_id")

        def _consume_from_location(location: WorldLocation) -> WorldLocation:
            return location.model_copy(
                update={"items": _deduct_stack(location.items, event.item_id, event.qty)}
            )

        world = _replace_location(state.world, event.location_id, _consume_from_location)
        return state.model_copy(update={"world": world})

    if isinstance(event, EnemyGroupDamaged):
        def _apply_damage(group: EnemyGroup) -> EnemyGroup:
            if group.current_hp <= 0:
                raise ValueError(f"enemy group already defeated: {group.id}")
            if event.current_hp < 0 or event.current_hp >= group.current_hp:
                raise ValueError(f"invalid enemy HP after damage: {group.id}")
            return group.model_copy(update={"current_hp": event.current_hp})

        world = _replace_enemy_group(state.world, event.enemy_group_id, _apply_damage)
        return state.model_copy(update={"world": world})

    if isinstance(event, ObjectiveCompleted):
        def _complete_objective(objective: Objective) -> Objective:
            if objective.status == "completed":
                return objective
            return objective.model_copy(update={"status": "completed"})

        world = _replace_objective(state.world, event.objective_id, _complete_objective)
        return state.model_copy(update={"world": world})

    if isinstance(event, QuestCompleted):
        if state.quest.id != event.quest_id:
            raise ValueError(f"quest id mismatch: {event.quest_id}")
        if state.quest.status == "completed":
            return state
        quest = state.quest.model_copy(update={"status": "completed"})
        return state.model_copy(update={"quest": quest})

    if isinstance(event, SummaryUpdated):
        return state.model_copy(
            update={
                "summary": event.summary,
                "recap_through_turn": event.through_turn,
            }
        )

    raise TypeError(f"unsupported event type: {type(event)!r}")


def fold_events(events: list[Event]) -> GameState:
    """Replay an Event log from empty state into a Snapshot."""
    if not events:
        raise ValueError("cannot fold an empty event log")

    state: GameState | None = None
    for event in events:
        state = apply_event(state, event)
    assert state is not None
    return state
