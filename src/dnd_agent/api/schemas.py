"""HTTP request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from dnd_agent.domain.events import Event
from dnd_agent.domain.models import GameState


class CreateSessionRequest(BaseModel):
    scenario_id: str = "goblin_cave"
    character_id: str | None = None
    rng_seed: int | None = Field(default=None, ge=0)


class EventListResponse(BaseModel):
    session_id: str
    events: list[Event]


# Re-export GameState as the Session Snapshot response body.
SessionStateResponse = GameState
