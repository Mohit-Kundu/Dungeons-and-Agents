"""Load predefined characters and scenarios from the content/ directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from dnd_agent.domain.models import (
    Character,
    EnemyGroup,
    Interactable,
    InventoryContainsPredicate,
    Item,
    LocationVisitedPredicate,
    Objective,
    ObjectivePredicate,
    PlayableWorld,
    Quest,
    WorldLocation,
)


def content_root() -> Path:
    """Repo `content/` directory."""
    # src/dnd_agent/content/loader.py → repo root
    return Path(__file__).resolve().parents[3] / "content"


class ScenarioEnemyGroup(BaseModel):
    id: str
    name: str
    location_id: str
    count: int = Field(ge=1)
    hp_per_enemy: int = Field(ge=1)
    resolution_damage: int = Field(ge=1)


class ScenarioObjective(BaseModel):
    id: str
    title: str
    summary: str = ""
    predicate: ObjectivePredicate


class ScenarioLocation(BaseModel):
    id: str
    name: str
    description: str = ""
    exits: list[str] = Field(default_factory=list)
    interactables: list[Interactable] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    title: str
    starting_location: str
    character_id: str
    quest: Quest
    intro: str = ""
    locations: list[ScenarioLocation] = Field(default_factory=list)
    enemy_groups: list[ScenarioEnemyGroup] = Field(default_factory=list)
    objectives: list[ScenarioObjective] = Field(default_factory=list)
    beats: list[str] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def validate_playable_world(self) -> Scenario:
        location_ids = [location.id for location in self.locations]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("duplicate location id")

        location_id_set = set(location_ids)
        if self.locations and self.starting_location not in location_id_set:
            raise ValueError(
                f"starting location {self.starting_location!r} is not a known location"
            )

        for location in self.locations:
            for exit_id in location.exits:
                if exit_id not in location_id_set:
                    raise ValueError(f"unknown exit target: {exit_id}")

        enemy_ids = [group.id for group in self.enemy_groups]
        if len(enemy_ids) != len(set(enemy_ids)):
            raise ValueError("duplicate enemy group id")
        for group in self.enemy_groups:
            if group.location_id not in location_id_set:
                raise ValueError(
                    f"enemy group location {group.location_id!r} is not a known location"
                )

        item_ids = [item.id for location in self.locations for item in location.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("duplicate item id")
        item_id_set = set(item_ids)

        interactable_ids = [
            interactable.id
            for location in self.locations
            for interactable in location.interactables
        ]
        if len(interactable_ids) != len(set(interactable_ids)):
            raise ValueError("duplicate interactable id")

        objective_ids = [objective.id for objective in self.objectives]
        if len(objective_ids) != len(set(objective_ids)):
            raise ValueError("duplicate objective id")

        for objective in self.objectives:
            predicate = objective.predicate
            if isinstance(predicate, LocationVisitedPredicate):
                if predicate.location_id not in location_id_set:
                    raise ValueError(
                        f"objective location {predicate.location_id!r} is not a known location"
                    )
            elif isinstance(predicate, InventoryContainsPredicate):
                if predicate.item_id not in item_id_set:
                    raise ValueError(
                        f"objective item {predicate.item_id!r} is not a known playable item"
                    )
            else:
                if predicate.enemy_group_id not in set(enemy_ids):
                    raise ValueError(
                        f"objective enemy group {predicate.enemy_group_id!r} "
                        "is not a known enemy group"
                    )
        return self

    def briefing(self) -> str:
        """Text seeded into GameState.summary for the DM Agent."""
        parts: list[str] = []
        if self.intro.strip():
            parts.append(self.intro.strip())
        if self.locations:
            lines = ["Known locations:"]
            for location in self.locations:
                detail = f" — {location.description}" if location.description else ""
                lines.append(f"- {location.name}{detail}")
            parts.append("\n".join(lines))
        if self.beats:
            lines = ["Suggested beats:"]
            for index, beat in enumerate(self.beats, start=1):
                lines.append(f"{index}. {beat}")
            parts.append("\n".join(lines))
        if self.notes.strip():
            parts.append(self.notes.strip())
        return "\n\n".join(parts)

    def build_world(self, *, current_location_id: str | None = None) -> PlayableWorld:
        """Build runtime PlayableWorld seeded for a Session."""
        location_id = current_location_id or self.starting_location
        visited = [location_id] if location_id else []
        return PlayableWorld(
            locations=[
                WorldLocation(
                    id=location.id,
                    name=location.name,
                    description=location.description,
                    exits=list(location.exits),
                    interactables=[
                        interactable.model_copy(deep=True)
                        for interactable in location.interactables
                    ],
                    items=[item.model_copy(deep=True) for item in location.items],
                )
                for location in self.locations
            ],
            enemy_groups=[
                EnemyGroup(
                    id=group.id,
                    name=group.name,
                    location_id=group.location_id,
                    count=group.count,
                    hp_per_enemy=group.hp_per_enemy,
                    resolution_damage=group.resolution_damage,
                    current_hp=group.count * group.hp_per_enemy,
                )
                for group in self.enemy_groups
            ],
            objectives=[
                Objective(
                    id=objective.id,
                    title=objective.title,
                    summary=objective.summary,
                    predicate=objective.predicate,
                    status="active",
                )
                for objective in self.objectives
            ],
            visited_location_ids=visited,
        )

    def resolve_location_id(self, location: str) -> str | None:
        """Map a location id or display name onto a stable location id."""
        for candidate in self.locations:
            if location == candidate.id or location == candidate.name:
                return candidate.id
        return None


@lru_cache(maxsize=32)
def load_character(character_id: str) -> Character:
    path = content_root() / "characters" / f"{character_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"character not found: {character_id}")
    return Character.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def load_scenario(scenario_id: str) -> Scenario:
    path = content_root() / "scenarios" / f"{scenario_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"scenario not found: {scenario_id}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Scenario.model_validate(data)
