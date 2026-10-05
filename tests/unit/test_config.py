"""Seam: Settings loads documented defaults from the environment."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dnd_agent.config import Settings


def _clear_dnd_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("DND_"):
            monkeypatch.delenv(key, raising=False)


def test_settings_have_documented_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_dnd_env(monkeypatch)

    settings = Settings()

    assert settings.model == "google-gla:gemini-2.5-flash"
    assert settings.database_url == "sqlite:///./data/dnd_agent.db"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert settings.api_base_url == "http://127.0.0.1:8000"
    assert settings.memory_recent_turns == 8
    assert settings.summary_every_n_turns == 5
    assert settings.max_tool_calls_per_turn == 12
    assert settings.agent_retries == 2
    assert settings.openai_base_url is None
    assert settings.ollama_base_url == "http://127.0.0.1:11434/v1"


def test_settings_read_model_from_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_dnd_env(monkeypatch)
    monkeypatch.setenv("DND_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("DND_API_PORT", "9000")

    settings = Settings()

    assert settings.model == "openai:gpt-4.1-mini"
    assert settings.api_port == 9000
