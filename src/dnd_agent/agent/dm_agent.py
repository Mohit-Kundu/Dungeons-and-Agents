"""PydanticAI DM Agent factory."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from dnd_agent.agent.deps import TurnDeps
from dnd_agent.agent.prompts import DM_SYSTEM_PROMPT
from dnd_agent.agent.tools import get_state, move_to, roll_dice, skill_check_tool


def build_dm_agent(model: Model | str) -> Agent[TurnDeps, str]:
    agent: Agent[TurnDeps, str] = Agent(
        model,
        deps_type=TurnDeps,
        system_prompt=DM_SYSTEM_PROMPT,
        retries=2,
    )
    agent.tool(get_state)
    agent.tool(roll_dice)
    agent.tool(name="skill_check")(skill_check_tool)
    agent.tool(move_to)
    return agent
