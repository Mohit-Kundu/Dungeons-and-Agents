"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from pydantic_ai.models import Model

from dnd_agent.api.routes.sessions import router as sessions_router
from dnd_agent.api.routes.turns import router as turns_router
from dnd_agent.config import Settings, get_settings
from dnd_agent.store.event_store import EventStore


def database_path(settings: Settings) -> Path:
    url = settings.database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError(f"unsupported database_url: {url}")
    return Path(url.removeprefix(prefix))


def create_app(
    *,
    settings: Settings | None = None,
    store: EventStore | None = None,
    turn_model: Model | str | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app_store = store if store is not None else EventStore(database_path(settings))
        await app_store.open()
        app.state.store = app_store
        app.state.turn_model = turn_model
        yield

    app = FastAPI(title="D&D Agent", version="0.1.0", lifespan=lifespan)
    app.state.turn_model = turn_model
    app.include_router(sessions_router)
    app.include_router(turns_router)
    return app
