"""SSE / stream payload types for a playable Turn (D-005)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from dnd_agent.domain.models import GameState
from dnd_agent.world.travel import ReachableDestination

ROLL_EVENT_TYPES = frozenset(
    {
        "dice_rolled",
        "skill_check_resolved",
        "saving_throw_resolved",
        "short_rest_completed",
    }
)

STATE_EVENT_TYPES = frozenset(
    {
        "condition_added",
        "condition_removed",
        "short_rest_completed",
        "long_rest_completed",
        "location_changed",
        "item_taken",
        "item_consumed",
        "enemy_group_damaged",
    }
)


class NarrationDelta(BaseModel):
    type: Literal["narration_delta"] = "narration_delta"
    text: str


class ProgressEvent(BaseModel):
    """Player-facing Turn phase for live CLI anticipation (D-018)."""

    type: Literal["progress"] = "progress"
    phase: Literal["awaiting_dm", "rolling", "updating_recap"]
    label: str


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    tool_name: str
    args: dict[str, Any]


class RollEvent(BaseModel):
    type: Literal["roll"] = "roll"
    event: dict[str, Any]


class StateChangedEvent(BaseModel):
    type: Literal["state_changed"] = "state_changed"
    event: dict[str, Any]


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    turn_number: int
    status: str
    state: GameState
    narration: str = ""
    reachable: list[ReachableDestination] = Field(default_factory=list)


TurnStreamEvent = Annotated[
    NarrationDelta
    | ProgressEvent
    | ToolCallEvent
    | RollEvent
    | StateChangedEvent
    | ErrorEvent
    | DoneEvent,
    Field(discriminator="type"),
]
