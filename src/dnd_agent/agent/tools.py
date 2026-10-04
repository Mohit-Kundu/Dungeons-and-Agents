"""Typed tools the DM Agent may call. Each successful tool emits Events."""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from dnd_agent.agent.deps import TurnDeps
from dnd_agent.domain.events import DiceRolled, LocationChanged, SkillCheckResolved
from dnd_agent.rules.checks import skill_check
from dnd_agent.rules.dice import DiceRng, roll


async def get_state(ctx: RunContext[TurnDeps]) -> dict[str, Any]:
    """Return the current GameState Snapshot for this Session."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    return state.model_dump(mode="json")


async def roll_dice(
    ctx: RunContext[TurnDeps],
    expression: str,
    reason: str = "",
) -> dict[str, Any]:
    """Roll dice with a seeded RNG. Never invent numbers in narration — call this."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        rng = DiceRng(state.rng_seed)
        result = roll(expression, rng)
        next_seed = rng.next_seed()
    except ValueError as exc:
        return {"error": str(exc)}

    event = DiceRolled(
        expression=result.expression,
        rolls=list(result.rolls),
        kept=list(result.kept),
        modifier=result.modifier,
        total=result.total,
        reason=reason,
        next_rng_seed=next_seed,
    )
    await ctx.deps.store.append_event(ctx.deps.session_id, event)
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")


async def skill_check_tool(
    ctx: RunContext[TurnDeps],
    skill: str,
    dc: int,
    reason: str = "",
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict[str, Any]:
    """Resolve a skill Check with real dice. Use before narrating success or failure."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        rng = DiceRng(state.rng_seed)
        result = skill_check(
            state.character,
            skill=skill,
            dc=dc,
            rng=rng,
            advantage=advantage,
            disadvantage=disadvantage,
            reason=reason,
        )
        next_seed = rng.next_seed()
    except ValueError as exc:
        return {"error": str(exc)}

    event = SkillCheckResolved(
        skill=result.skill,
        ability=result.ability,
        dc=result.dc,
        expression=result.expression,
        rolls=list(result.rolls),
        d20=result.d20,
        modifier=result.modifier,
        total=result.total,
        success=result.success,
        reason=result.reason,
        next_rng_seed=next_seed,
    )
    await ctx.deps.store.append_event(ctx.deps.session_id, event)
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")


async def move_to(
    ctx: RunContext[TurnDeps],
    location: str,
    reason: str = "",
) -> dict[str, Any]:
    """Move the party to a new location after the fiction supports it."""
    location = location.strip()
    if not location:
        return {"error": "location must not be empty"}
    event = LocationChanged(location=location, reason=reason)
    try:
        await ctx.deps.store.append_event(ctx.deps.session_id, event)
    except KeyError as exc:
        return {"error": str(exc)}
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")
