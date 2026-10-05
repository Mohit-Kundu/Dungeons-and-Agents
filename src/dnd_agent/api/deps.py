"""Shared FastAPI helpers for Session-scoped services."""

from __future__ import annotations

from fastapi import Request
from pydantic_ai.models import Model

from dnd_agent.agent.providers import resolve_model
from dnd_agent.agent.recap import RecapService
from dnd_agent.config import get_settings
from dnd_agent.services.recap_refresh import RecapRefreshService
from dnd_agent.services.session_locks import SessionLockRegistry
from dnd_agent.store.event_store import EventStore


def store_from_app(request: Request) -> EventStore:
    store = getattr(request.app.state, "store", None)
    if not isinstance(store, EventStore):
        raise RuntimeError("EventStore is not configured on the app")
    return store


def locks_from_app(request: Request) -> SessionLockRegistry:
    locks = getattr(request.app.state, "session_locks", None)
    if not isinstance(locks, SessionLockRegistry):
        locks = SessionLockRegistry()
        request.app.state.session_locks = locks
    return locks


def recap_model_from_app(request: Request) -> Model | str | None:
    configured = getattr(request.app.state, "recap_model", None)
    if configured is not None:
        return configured  # type: ignore[no-any-return]
    turn_model = getattr(request.app.state, "turn_model", None)
    if turn_model is not None:
        return turn_model  # type: ignore[no-any-return]
    return None


def recap_refresh_from_app(request: Request) -> RecapRefreshService:
    model = recap_model_from_app(request)
    recap = RecapService(model if model is not None else resolve_model(get_settings()))
    return RecapRefreshService(
        store=store_from_app(request),
        recap=recap,
        locks=locks_from_app(request),
    )
