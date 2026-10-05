"""Session HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from dnd_agent.api.deps import recap_refresh_from_app, store_from_app
from dnd_agent.api.schemas import (
    CreateSessionRequest,
    EventListResponse,
    LatestTurn,
    RecapRefreshResponse,
    SessionOverviewResponse,
    SessionStateResponse,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionStateResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    request: Request,
) -> SessionStateResponse:
    store = store_from_app(request)
    return await store.create_session(
        scenario_id=body.scenario_id,
        character_id=body.character_id,
        rng_seed=body.rng_seed,
    )


@router.get("/{session_id}/state", response_model=SessionStateResponse)
async def get_state(session_id: str, request: Request) -> SessionStateResponse:
    store = store_from_app(request)
    state = await store.get_snapshot(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    return state


@router.get("/{session_id}/events", response_model=EventListResponse)
async def get_events(session_id: str, request: Request) -> EventListResponse:
    store = store_from_app(request)
    state = await store.get_snapshot(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    events = await store.list_events(session_id)
    return EventListResponse(session_id=session_id, events=events)


@router.get("/{session_id}/overview", response_model=SessionOverviewResponse)
async def get_overview(session_id: str, request: Request) -> SessionOverviewResponse:
    store = store_from_app(request)
    if await store.get_snapshot(session_id) is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    # Restore path: refresh Recap for played Sessions before displaying.
    refreshed = await recap_refresh_from_app(request).refresh(session_id)
    latest = await store.get_latest_turn(session_id)
    return SessionOverviewResponse(
        state=refreshed.state,
        latest_turn=LatestTurn.model_validate(latest) if latest is not None else None,
        refreshed=refreshed.refreshed,
        refresh_failed=refreshed.failed,
    )


@router.post("/{session_id}/recap", response_model=RecapRefreshResponse)
async def refresh_recap(session_id: str, request: Request) -> RecapRefreshResponse:
    store = store_from_app(request)
    if await store.get_snapshot(session_id) is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    result = await recap_refresh_from_app(request).refresh(session_id)
    return RecapRefreshResponse(
        state=result.state,
        refreshed=result.refreshed,
        failed=result.failed,
    )
