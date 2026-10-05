"""Opt-in live provider smokes. Never required for the normal suite.

Run with:
  DND_LIVE_SMOKE=1 uv run pytest -m live
"""

from __future__ import annotations

import os

import pytest
from pydantic_ai import Agent

from dnd_agent.agent.providers import resolve_model
from dnd_agent.config import Settings

pytestmark = pytest.mark.live


def _require_live() -> None:
    if os.environ.get("DND_LIVE_SMOKE") != "1":
        pytest.skip("set DND_LIVE_SMOKE=1 to run live provider smokes")


@pytest.mark.asyncio
async def test_live_gemini_smoke() -> None:
    _require_live()
    settings = Settings()
    if not settings.gemini_api_key:
        pytest.skip("DND_GEMINI_API_KEY not set")
    if not settings.model.startswith(("google-gla:", "google:", "gemini:")):
        settings = settings.model_copy(
            update={"model": "google-gla:gemini-2.5-flash"}
        )
    model = resolve_model(settings)
    agent: Agent[None, str] = Agent(model, output_type=str)
    result = await agent.run("Reply with exactly the word: pong")
    assert "pong" in result.output.lower()


@pytest.mark.asyncio
async def test_live_openai_smoke() -> None:
    _require_live()
    settings = Settings()
    if not settings.openai_api_key:
        pytest.skip("DND_OPENAI_API_KEY not set")
    model_id = (
        settings.model if settings.model.startswith("openai:") else "openai:gpt-4.1-mini"
    )
    settings = settings.model_copy(update={"model": model_id})
    model = resolve_model(settings)
    agent: Agent[None, str] = Agent(model, output_type=str)
    result = await agent.run("Reply with exactly the word: pong")
    assert "pong" in result.output.lower()


@pytest.mark.asyncio
async def test_live_ollama_smoke() -> None:
    _require_live()
    settings = Settings()
    settings = settings.model_copy(update={"model": "ollama:llama3.2"})
    model = resolve_model(settings)
    agent: Agent[None, str] = Agent(model, output_type=str)
    try:
        result = await agent.run("Reply with exactly the word: pong")
    except Exception as exc:  # noqa: BLE001 - local daemon may be down
        pytest.skip(f"ollama unavailable: {exc}")
    assert "pong" in result.output.lower()
