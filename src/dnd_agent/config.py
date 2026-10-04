"""Application settings loaded from environment variables and optional `.env`."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API, CLI, store, and DM agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DND_",
        extra="ignore",
    )

    model: str = "google-gla:gemini-2.5-flash"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434/v1"

    database_url: str = "sqlite:///./data/dnd_agent.db"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    memory_recent_turns: int = 8
    summary_every_n_turns: int = 5
    max_tool_calls_per_turn: int = 12


def get_settings() -> Settings:
    """Load settings from the current environment."""
    return Settings()
