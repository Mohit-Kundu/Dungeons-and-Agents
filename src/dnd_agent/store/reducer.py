"""Pure Reducer: Events → GameState."""

from __future__ import annotations

from dnd_agent.domain.events import (
    DiceRolled,
    Event,
    LocationChanged,
    SessionCreated,
    SkillCheckResolved,
)
from dnd_agent.domain.models import GameState


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
            summary="",
        )

    if state is None:
        raise ValueError(f"{type(event).__name__} requires an existing GameState")

    if isinstance(event, DiceRolled):
        return state.model_copy(update={"rng_seed": event.next_rng_seed})

    if isinstance(event, SkillCheckResolved):
        return state.model_copy(update={"rng_seed": event.next_rng_seed})

    if isinstance(event, LocationChanged):
        return state.model_copy(update={"location": event.location})

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
