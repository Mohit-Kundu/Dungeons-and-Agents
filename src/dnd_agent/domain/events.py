"""Immutable Event types appended to the Session log."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from dnd_agent.domain.models import Character, Quest


class SessionCreated(BaseModel):
    type: Literal["session_created"] = "session_created"
    session_id: str
    scenario_id: str
    character: Character
    location: str
    quest: Quest
    rng_seed: int


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


class LocationChanged(BaseModel):
    type: Literal["location_changed"] = "location_changed"
    location: str
    reason: str = ""


Event = Annotated[
    SessionCreated | DiceRolled | SkillCheckResolved | LocationChanged,
    Field(discriminator="type"),
]

EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(
    SessionCreated | DiceRolled | SkillCheckResolved | LocationChanged
)
