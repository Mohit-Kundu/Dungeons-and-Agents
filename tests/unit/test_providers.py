"""Seam: resolve_model maps Settings to provider Models without network I/O."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel

from dnd_agent.agent.providers import ProviderConfigError, resolve_model
from dnd_agent.config import Settings


def _clear_dnd_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("DND_"):
            monkeypatch.delenv(key, raising=False)


def test_default_settings_resolve_to_gemini(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_dnd_env(monkeypatch)
    monkeypatch.setenv("DND_GEMINI_API_KEY", "test-gemini-key")

    model = resolve_model(Settings())

    assert isinstance(model, GoogleModel)
    assert model.model_name == "gemini-2.5-flash"


def test_openai_model_uses_api_key_and_optional_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_dnd_env(monkeypatch)
    monkeypatch.setenv("DND_MODEL", "openai:luna")
    monkeypatch.setenv("DND_OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("DND_OPENAI_BASE_URL", "https://api.example.com/v1")

    model = resolve_model(Settings())

    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "luna"
    assert "api.example.com" in model.base_url


def test_ollama_model_uses_configured_base_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_dnd_env(monkeypatch)
    monkeypatch.setenv("DND_MODEL", "ollama:llama3.2")
    monkeypatch.setenv("DND_OLLAMA_BASE_URL", "http://localhost:11434/v1")

    model = resolve_model(Settings())

    assert isinstance(model, OllamaModel)
    assert model.model_name == "llama3.2"


def test_missing_gemini_key_fails_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_dnd_env(monkeypatch)

    with pytest.raises(ProviderConfigError, match="DND_GEMINI_API_KEY"):
        resolve_model(Settings())


def test_missing_openai_key_fails_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_dnd_env(monkeypatch)
    monkeypatch.setenv("DND_MODEL", "openai:gpt-4.1-mini")

    with pytest.raises(ProviderConfigError, match="DND_OPENAI_API_KEY"):
        resolve_model(Settings())


def test_unsupported_provider_fails_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_dnd_env(monkeypatch)
    monkeypatch.setenv("DND_MODEL", "anthropic:claude-sonnet")

    with pytest.raises(ProviderConfigError, match="unsupported provider"):
        resolve_model(Settings())
