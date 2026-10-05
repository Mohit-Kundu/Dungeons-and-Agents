"""PydanticAI DM Agent factory."""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models import Model

from dnd_agent.agent.deps import TurnDeps
from dnd_agent.agent.prompts import DM_SYSTEM_PROMPT
from dnd_agent.agent.tools import (
    add_condition,
    get_state,
    long_rest_tool,
    move_to,
    remove_condition,
    resolve_enemy,
    roll_dice,
    saving_throw_tool,
    short_rest_tool,
    skill_check_tool,
    take_item,
    use_item,
)


def build_dm_agent(model: Model | str, *, retries: int = 2) -> Agent[TurnDeps, str]:
    agent: Agent[TurnDeps, str] = Agent(
        model,
        deps_type=TurnDeps,
        system_prompt=DM_SYSTEM_PROMPT,
        retries=retries,
    )
    agent.tool(get_state)
    agent.tool(roll_dice)
    agent.tool(name="skill_check")(skill_check_tool)
    agent.tool(name="saving_throw")(saving_throw_tool)
    agent.tool(add_condition)
    agent.tool(remove_condition)
    agent.tool(name="short_rest")(short_rest_tool)
    agent.tool(name="long_rest")(long_rest_tool)
    agent.tool(move_to)
    agent.tool(take_item)
    agent.tool(use_item)
    agent.tool(resolve_enemy)
    return agent
