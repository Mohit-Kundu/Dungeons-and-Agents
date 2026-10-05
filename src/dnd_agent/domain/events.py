"""Immutable Event types appended to the Session log."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from dnd_agent.domain.models import Character, PlayableWorld, Quest


class SessionCreated(BaseModel):
    type: Literal["session_created"] = "session_created"
    session_id: str
    scenario_id: str
    character: Character
    location: str
    quest: Quest
    rng_seed: int
    summary: str = ""
    world: PlayableWorld = Field(default_factory=PlayableWorld)


class DiceRolled(BaseModel):
    type: Literal["dice_rolled"] = "dice_rolled"
    expression: str
    rolls: list[int]
    kept: list[int]
    modifier: int
    total: int
    reason: str = ""
    next_rng_seed: int


class SkillCheckResolved(BaseModel):
    type: Literal["skill_check_resolved"] = "skill_check_resolved"
    skill: str
    ability: str
    dc: int
    expression: str
    rolls: list[int]
    d20: int
    modifier: int
    total: int
    success: bool
    reason: str = ""
    next_rng_seed: int


class SavingThrowResolved(BaseModel):
    type: Literal["saving_throw_resolved"] = "saving_throw_resolved"
    ability: str
    dc: int
    expression: str
    rolls: list[int]
    d20: int
    modifier: int
    total: int
    success: bool
    reason: str = ""
    next_rng_seed: int


class ConditionAdded(BaseModel):
    type: Literal["condition_added"] = "condition_added"
    condition: str
    reason: str = ""


class ConditionRemoved(BaseModel):
    type: Literal["condition_removed"] = "condition_removed"
    condition: str
    reason: str = ""


class ShortRestCompleted(BaseModel):
    type: Literal["short_rest_completed"] = "short_rest_completed"
    hit_dice_spent: int
    hit_dice_rolls: list[int]
    hp_recovered: int
    hp_after: int
    hit_dice_remaining: int
    reason: str = ""
    next_rng_seed: int


class LongRestCompleted(BaseModel):
    type: Literal["long_rest_completed"] = "long_rest_completed"
    hp_after: int
    hit_dice_restored: int
    hit_dice_remaining: int
    conditions_cleared: list[str]
    reason: str = ""


class LocationChanged(BaseModel):
    type: Literal["location_changed"] = "location_changed"
    location: str
    reason: str = ""


class SummaryUpdated(BaseModel):
    """Immutable Recap write into GameState.summary."""

    type: Literal["summary_updated"] = "summary_updated"
    summary: str
    reason: str = ""


Event = Annotated[
    SessionCreated
    | DiceRolled
    | SkillCheckResolved
    | SavingThrowResolved
    | ConditionAdded
    | ConditionRemoved
    | ShortRestCompleted
    | LongRestCompleted
    | LocationChanged
    | SummaryUpdated,
    Field(discriminator="type"),
]

EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(
    SessionCreated
    | DiceRolled
    | SkillCheckResolved
    | SavingThrowResolved
    | ConditionAdded
    | ConditionRemoved
    | ShortRestCompleted
    | LongRestCompleted
    | LocationChanged
    | SummaryUpdated
)
