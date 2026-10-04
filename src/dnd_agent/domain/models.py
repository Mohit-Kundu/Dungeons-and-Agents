"""Validated domain models for characters and GameState."""

from __future__ import annotations

from typing import Literal

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


class Quest(BaseModel):
    id: str
    title: str
    summary: str
    status: Literal["active", "completed", "failed"] = "active"


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
