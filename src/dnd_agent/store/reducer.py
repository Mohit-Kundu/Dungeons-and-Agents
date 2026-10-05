"""Pure Reducer: Events → GameState."""

from __future__ import annotations

from dnd_agent.domain.events import (
    ConditionAdded,
    ConditionRemoved,
    DiceRolled,
    Event,
    LocationChanged,
    LongRestCompleted,
    SavingThrowResolved,
    SessionCreated,
    ShortRestCompleted,
    SkillCheckResolved,
    SummaryUpdated,
)
from dnd_agent.domain.models import Character, GameState


def _with_character(state: GameState, character: Character, **updates: object) -> GameState:
    return state.model_copy(update={"character": character, **updates})


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

    if isinstance(event, SummaryUpdated):
        return state.model_copy(update={"summary": event.summary})

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
