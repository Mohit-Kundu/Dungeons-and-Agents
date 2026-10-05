"""Resolve Settings into a concrete PydanticAI Model (D-016)."""

from __future__ import annotations

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.providers.openai import OpenAIProvider

from dnd_agent.config import Settings

GEMINI_PROVIDERS = frozenset({"google-gla", "google", "gemini"})
OPENAI_PROVIDERS = frozenset({"openai", "openai-chat"})
OLLAMA_PROVIDERS = frozenset({"ollama"})


class ProviderConfigError(ValueError):
    """Invalid or incomplete provider configuration."""


def parse_model_string(model: str) -> tuple[str, str]:
    cleaned = model.strip()
    if ":" not in cleaned:
        raise ProviderConfigError(
            f"invalid model string (expected provider:model): {model}"
        )
    provider, model_name = cleaned.split(":", 1)
    provider_key = provider.strip().lower()
    name = model_name.strip()
    if not provider_key or not name:
        raise ProviderConfigError(
            f"invalid model string (expected provider:model): {model}"
        )
    return provider_key, name


def resolve_model(settings: Settings) -> Model:
    """Build a PydanticAI Model from Settings. Does not call the network."""
    provider, model_name = parse_model_string(settings.model)

    if provider in GEMINI_PROVIDERS:
        if not settings.gemini_api_key:
            raise ProviderConfigError(
                "DND_GEMINI_API_KEY is required for Gemini models"
            )
        return GoogleModel(
            model_name,
            provider=GoogleProvider(api_key=settings.gemini_api_key),
        )

    if provider in OPENAI_PROVIDERS:
        if not settings.openai_api_key:
            raise ProviderConfigError(
                "DND_OPENAI_API_KEY is required for OpenAI models"
            )
        return OpenAIChatModel(
            model_name,
            provider=OpenAIProvider(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            ),
        )

    if provider in OLLAMA_PROVIDERS:
        return OllamaModel(
            model_name,
            provider=OllamaProvider(base_url=settings.ollama_base_url),
        )

    raise ProviderConfigError(f"unsupported provider: {provider}")
