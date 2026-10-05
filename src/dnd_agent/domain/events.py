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


class ItemTaken(BaseModel):
    """Transfer a portable Item stack from a Location into inventory."""

    type: Literal["item_taken"] = "item_taken"
    item_id: str
    name: str
    qty: int = Field(ge=1)
    from_location_id: str
    consumable: bool = False
    reason: str = ""


class ItemConsumed(BaseModel):
    """Deterministic consumable quantity deduction from inventory or surroundings."""

    type: Literal["item_consumed"] = "item_consumed"
    item_id: str
    qty: int = Field(ge=1)
    source: Literal["inventory", "location"]
    location_id: str | None = None
    reason: str = ""


class EnemyGroupDamaged(BaseModel):
    """Deterministic aggregate HP deduction for a present Enemy Group."""

    type: Literal["enemy_group_damaged"] = "enemy_group_damaged"
    enemy_group_id: str
    damage: int = Field(ge=1)
    current_hp: int = Field(ge=0)
    reason: str = ""


class ObjectiveCompleted(BaseModel):
    """Mark one Objective complete after its predicate becomes true."""

    type: Literal["objective_completed"] = "objective_completed"
    objective_id: str
    title: str = ""
    reason: str = ""


class QuestCompleted(BaseModel):
    """Mark the Session Quest complete after all Objectives are complete."""

    type: Literal["quest_completed"] = "quest_completed"
    quest_id: str
    title: str = ""
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
    | ItemTaken
    | ItemConsumed
    | EnemyGroupDamaged
    | ObjectiveCompleted
    | QuestCompleted
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
    | ItemTaken
    | ItemConsumed
    | EnemyGroupDamaged
    | ObjectiveCompleted
    | QuestCompleted
    | SummaryUpdated
)
