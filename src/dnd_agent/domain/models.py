"""Validated domain models for characters and GameState."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class AbilityScores(BaseModel):
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int

    @field_validator(
        "strength",
        "dexterity",
        "constitution",
        "intelligence",
        "wisdom",
        "charisma",
    )
    @classmethod
    def score_in_range(cls, value: int) -> int:
        if not 1 <= value <= 30:
            raise ValueError("ability score must be between 1 and 30")
        return value


class Item(BaseModel):
    id: str
    name: str
    qty: int = Field(ge=1)
    consumable: bool = False


class Quest(BaseModel):
    id: str
    title: str
    summary: str
    status: Literal["active", "completed", "failed"] = "active"


class Interactable(BaseModel):
    """A non-portable Playable Fact in a Location's surroundings."""

    id: str
    name: str
    description: str = ""


class WorldLocation(BaseModel):
    id: str
    name: str
    description: str = ""
    exits: list[str] = Field(default_factory=list)
    interactables: list[Interactable] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)


class EnemyGroup(BaseModel):
    """Homogeneous enemies tracked by aggregate current HP."""

    id: str
    name: str
    location_id: str
    count: int = Field(ge=1)
    hp_per_enemy: int = Field(ge=1)
    resolution_damage: int = Field(ge=1)
    current_hp: int = Field(ge=0)

    @property
    def max_hp(self) -> int:
        return self.count * self.hp_per_enemy

    @property
    def remaining_count(self) -> int:
        if self.current_hp <= 0:
            return 0
        return (self.current_hp + self.hp_per_enemy - 1) // self.hp_per_enemy


class LocationVisitedPredicate(BaseModel):
    type: Literal["location_visited"] = "location_visited"
    location_id: str


class InventoryContainsPredicate(BaseModel):
    type: Literal["inventory_contains"] = "inventory_contains"
    item_id: str
    qty: int = Field(default=1, ge=1)


class EnemiesDefeatedPredicate(BaseModel):
    type: Literal["enemies_defeated"] = "enemies_defeated"
    enemy_group_id: str


ObjectivePredicate = Annotated[
    LocationVisitedPredicate | InventoryContainsPredicate | EnemiesDefeatedPredicate,
    Field(discriminator="type"),
]


class Objective(BaseModel):
    id: str
    title: str
    summary: str = ""
    predicate: ObjectivePredicate
    status: Literal["active", "completed", "failed"] = "active"


class PlayableWorld(BaseModel):
    """Authoritative Playable Facts seeded from a Scenario."""

    locations: list[WorldLocation] = Field(default_factory=list)
    enemy_groups: list[EnemyGroup] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    visited_location_ids: list[str] = Field(default_factory=list)

    def is_seeded(self) -> bool:
        return bool(self.locations)


class Character(BaseModel):
    id: str
    name: str
    level: int = Field(ge=1, le=20)
    class_name: str
    abilities: AbilityScores
    proficiency_bonus: int = Field(ge=2, le=6)
    proficient_skills: list[str] = Field(default_factory=list)
    max_hp: int = Field(ge=1)
    hp: int
    hit_die: int = Field(ge=4, le=12)
    hit_dice_total: int = Field(ge=1)
    hit_dice_remaining: int = Field(ge=0)
    armor_class: int = Field(ge=1)
    inventory: list[Item] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)

    @field_validator("hp")
    @classmethod
    def hp_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("hp cannot be negative")
        return value


class GameState(BaseModel):
    session_id: str
    scenario_id: str
    character: Character
    location: str
    quest: Quest
    rng_seed: int
    summary: str = ""
    world: PlayableWorld = Field(default_factory=PlayableWorld)
