"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from dnd_agent.api.routes.sessions import router as sessions_router
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
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app_store = store if store is not None else EventStore(database_path(settings))
        await app_store.open()
        app.state.store = app_store
        yield

    app = FastAPI(title="D&D Agent", version="0.1.0", lifespan=lifespan)
    app.include_router(sessions_router)
    return app
