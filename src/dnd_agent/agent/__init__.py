"""DM agent, tools, prompts, and provider wiring."""

from dnd_agent.agent.deps import TurnDeps
from dnd_agent.agent.dm_agent import build_dm_agent

__all__ = ["TurnDeps", "build_dm_agent"]
