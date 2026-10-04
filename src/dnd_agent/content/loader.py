"""Load predefined characters and scenarios from the content/ directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from dnd_agent.domain.models import Character, Quest


def content_root() -> Path:
    """Repo `content/` directory."""
    # src/dnd_agent/content/loader.py → repo root
    return Path(__file__).resolve().parents[3] / "content"


class Scenario(BaseModel):
    id: str
    title: str
    starting_location: str
    character_id: str
    quest: Quest
    intro: str = ""


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
