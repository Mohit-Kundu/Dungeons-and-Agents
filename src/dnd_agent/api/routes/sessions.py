"""Session HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from dnd_agent.api.schemas import (
    CreateSessionRequest,
    EventListResponse,
    SessionStateResponse,
)
from dnd_agent.store.event_store import EventStore

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _store(request: Request) -> EventStore:
    store = getattr(request.app.state, "store", None)
    if not isinstance(store, EventStore):
        raise RuntimeError("EventStore is not configured on the app")
    return store


@router.post("", response_model=SessionStateResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    request: Request,
) -> SessionStateResponse:
    store = _store(request)
    return await store.create_session(
        scenario_id=body.scenario_id,
        character_id=body.character_id,
        rng_seed=body.rng_seed,
    )


@router.get("/{session_id}/state", response_model=SessionStateResponse)
async def get_state(session_id: str, request: Request) -> SessionStateResponse:
    store = _store(request)
    state = await store.get_snapshot(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    return state


@router.get("/{session_id}/events", response_model=EventListResponse)
async def get_events(session_id: str, request: Request) -> EventListResponse:
    store = _store(request)
    state = await store.get_snapshot(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    events = await store.list_events(session_id)
    return EventListResponse(session_id=session_id, events=events)
