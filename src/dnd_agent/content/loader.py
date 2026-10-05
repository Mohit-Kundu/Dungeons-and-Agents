"""Load predefined characters and scenarios from the content/ directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from dnd_agent.domain.models import Character, Quest


def content_root() -> Path:
    """Repo `content/` directory."""
    # src/dnd_agent/content/loader.py → repo root
    return Path(__file__).resolve().parents[3] / "content"


class ScenarioLocation(BaseModel):
    name: str
    description: str = ""


class Scenario(BaseModel):
    id: str
    title: str
    starting_location: str
    character_id: str
    quest: Quest
    intro: str = ""
    locations: list[ScenarioLocation] = Field(default_factory=list)
    beats: list[str] = Field(default_factory=list)
    notes: str = ""

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
