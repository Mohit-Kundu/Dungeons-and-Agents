"""Dependencies injected into DM Agent tools for one Turn."""

from __future__ import annotations

from dataclasses import dataclass, field

from dnd_agent.domain.events import Event
from dnd_agent.store.event_store import EventStore


@dataclass
class TurnDeps:
    store: EventStore
    session_id: str
    events_this_turn: list[Event] = field(default_factory=list)
