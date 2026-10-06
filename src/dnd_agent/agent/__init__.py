"""DM agent, tools, prompts, provider wiring, and model cassettes."""

from dnd_agent.agent.cassette import (
    CassetteError,
    CassetteMode,
    ModelRole,
    StrictCassetteModel,
    wrap_model,
)
from dnd_agent.agent.deps import TurnDeps
from dnd_agent.agent.dm_agent import build_dm_agent
from dnd_agent.agent.providers import ProviderConfigError, resolve_model

__all__ = [
    "CassetteError",
    "CassetteMode",
    "ModelRole",
    "ProviderConfigError",
    "StrictCassetteModel",
    "TurnDeps",
    "build_dm_agent",
    "resolve_model",
    "wrap_model",
]
