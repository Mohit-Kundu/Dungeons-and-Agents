"""Immutable Event types appended to the Session log."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from dnd_agent.domain.models import Character, Quest


class SessionCreated(BaseModel):
    type: Literal["session_created"] = "session_created"
    session_id: str
    scenario_id: str
    character: Character
    location: str
    quest: Quest
    rng_seed: int


# Expand this union as new Event types land.
Event = SessionCreated
