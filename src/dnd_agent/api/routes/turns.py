"""Turn HTTP routes — SSE stream per D-005."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from dnd_agent.agent.providers import resolve_model
from dnd_agent.api.deps import locks_from_app, recap_refresh_from_app, store_from_app
from dnd_agent.api.schemas import RecapRefreshResponse
from dnd_agent.config import get_settings
from dnd_agent.services.stream_events import TurnStreamEvent
from dnd_agent.services.turns import TurnService
from dnd_agent.world.intent import CodeIntentService, IntentProposer, IntentService

router = APIRouter(tags=["turns"])


class PlayTurnRequest(BaseModel):
    player_text: str = Field(min_length=1)


def _turn_model(request: Request):
    return getattr(request.app.state, "turn_model", None)


def _intent_service(request: Request) -> IntentProposer:
    """Prefer an app-injected intent service; otherwise code for test models, LLM in prod."""
    configured = getattr(request.app.state, "intent_service", None)
    if configured is not None:
        return configured  # type: ignore[no-any-return]
    if _turn_model(request) is not None:
        # FunctionModel / injected DM models must not also drive intent extraction.
        return CodeIntentService()
    return IntentService(resolve_model(get_settings()))


def _sse_message(event: TurnStreamEvent) -> str:
    payload = event.model_dump(mode="json")
    data = json.dumps(payload, separators=(",", ":"))
    return f"event: {event.type}\ndata: {data}\n\n"


@router.post("/sessions/{session_id}/turns", response_model=None)
async def play_turn(
    session_id: str,
    body: PlayTurnRequest,
    request: Request,
) -> StreamingResponse | JSONResponse:
    store = store_from_app(request)
    if await store.get_snapshot(session_id) is None:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")

    text = body.player_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="player_text must not be empty")

    # In-play `/recap`: same refresh operation, no DM Turn.
    if text.casefold() == "/recap":
        result = await recap_refresh_from_app(request).refresh(session_id)
        payload = RecapRefreshResponse(
            state=result.state,
            refreshed=result.refreshed,
            failed=result.failed,
        )
        return JSONResponse(payload.model_dump(mode="json"))

    service = TurnService(
        store,
        model=_turn_model(request),
        locks=locks_from_app(request),
        intent=_intent_service(request),
    )

    async def event_publisher() -> AsyncIterator[str]:
        async for event in service.stream_turn(session_id, text):
            yield _sse_message(event)

    return StreamingResponse(
        event_publisher(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
