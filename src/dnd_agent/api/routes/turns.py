"""Turn HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from pydantic_ai.models import Model

from dnd_agent.domain.events import Event
from dnd_agent.domain.models import GameState
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore

router = APIRouter(tags=["turns"])


class PlayTurnRequest(BaseModel):
    player_text: str = Field(min_length=1)


class PlayTurnResponse(BaseModel):
    session_id: str
    turn_number: int
    player_text: str
    narration: str
    state: GameState
    events: list[Event]
    status: str


def _store(request: Request) -> EventStore:
    store = getattr(request.app.state, "store", None)
    if not isinstance(store, EventStore):
        raise RuntimeError("EventStore is not configured on the app")
    return store


def _turn_model(request: Request) -> Model | str | None:
    return getattr(request.app.state, "turn_model", None)


@router.post("/sessions/{session_id}/turns", response_model=PlayTurnResponse)
async def play_turn(
    session_id: str,
    body: PlayTurnRequest,
    request: Request,
) -> PlayTurnResponse:
    store = _store(request)
    model = _turn_model(request)
    service = TurnService(store, model=model)
    try:
        result = await service.run_turn(session_id, body.player_text)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PlayTurnResponse(
        session_id=result.session_id,
        turn_number=result.turn_number,
        player_text=result.player_text,
        narration=result.narration,
        state=result.state,
        events=result.events,
        status=result.status,
    )
