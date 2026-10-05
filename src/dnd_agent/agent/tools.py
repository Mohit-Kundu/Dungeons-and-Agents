"""Typed tools the DM Agent may call. Each successful tool emits Events."""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from dnd_agent.agent.deps import TurnDeps
from dnd_agent.domain.events import (
    ConditionAdded,
    ConditionRemoved,
    DiceRolled,
    ItemConsumed,
    ItemTaken,
    LocationChanged,
    LongRestCompleted,
    SavingThrowResolved,
    ShortRestCompleted,
    SkillCheckResolved,
)
from dnd_agent.rules.checks import skill_check
from dnd_agent.rules.conditions import normalize_condition
from dnd_agent.rules.dice import DiceRng, roll
from dnd_agent.rules.rests import long_rest, short_rest
from dnd_agent.rules.saves import saving_throw
from dnd_agent.world.inventory import plan_consume, plan_take, plan_use
from dnd_agent.world.travel import validate_travel


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
        next_seed = state.rng_seed if result.expression == "auto_fail" else rng.next_seed()
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


async def saving_throw_tool(
    ctx: RunContext[TurnDeps],
    ability: str,
    dc: int,
    reason: str = "",
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict[str, Any]:
    """Resolve a Save with real dice. Use before narrating success or failure."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        rng = DiceRng(state.rng_seed)
        result = saving_throw(
            state.character,
            ability=ability,
            dc=dc,
            rng=rng,
            advantage=advantage,
            disadvantage=disadvantage,
            reason=reason,
        )
        next_seed = rng.next_seed()
    except ValueError as exc:
        return {"error": str(exc)}

    event = SavingThrowResolved(
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


async def add_condition(
    ctx: RunContext[TurnDeps],
    condition: str,
    reason: str = "",
) -> dict[str, Any]:
    """Apply a known Condition to the Character."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        key = normalize_condition(condition)
    except ValueError as exc:
        return {"error": str(exc)}
    if key in state.character.conditions:
        return {"error": f"condition already present: {key}"}

    event = ConditionAdded(condition=key, reason=reason)
    await ctx.deps.store.append_event(ctx.deps.session_id, event)
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")


async def remove_condition(
    ctx: RunContext[TurnDeps],
    condition: str,
    reason: str = "",
) -> dict[str, Any]:
    """Remove a Condition from the Character."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        key = normalize_condition(condition)
    except ValueError as exc:
        return {"error": str(exc)}
    if key not in state.character.conditions:
        return {"error": f"condition not present: {key}"}

    event = ConditionRemoved(condition=key, reason=reason)
    await ctx.deps.store.append_event(ctx.deps.session_id, event)
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")


async def short_rest_tool(
    ctx: RunContext[TurnDeps],
    hit_dice_to_spend: int,
    reason: str = "",
) -> dict[str, Any]:
    """Take a short rest: spend hit dice to recover HP."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        rng = DiceRng(state.rng_seed)
        result = short_rest(
            state.character,
            hit_dice_to_spend=hit_dice_to_spend,
            rng=rng,
            reason=reason,
        )
        next_seed = rng.next_seed()
    except ValueError as exc:
        return {"error": str(exc)}

    event = ShortRestCompleted(
        hit_dice_spent=result.hit_dice_spent,
        hit_dice_rolls=list(result.hit_dice_rolls),
        hp_recovered=result.hp_recovered,
        hp_after=result.hp_after,
        hit_dice_remaining=result.hit_dice_remaining,
        reason=result.reason,
        next_rng_seed=next_seed,
    )
    await ctx.deps.store.append_event(ctx.deps.session_id, event)
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")


async def long_rest_tool(
    ctx: RunContext[TurnDeps],
    reason: str = "",
) -> dict[str, Any]:
    """Take a long rest: restore HP, some hit dice, and clear Conditions."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    result = long_rest(state.character, reason=reason)
    event = LongRestCompleted(
        hp_after=result.hp_after,
        hit_dice_restored=result.hit_dice_restored,
        hit_dice_remaining=result.hit_dice_remaining,
        conditions_cleared=list(result.conditions_cleared),
        reason=result.reason,
    )
    await ctx.deps.store.append_event(ctx.deps.session_id, event)
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")


async def move_to(
    ctx: RunContext[TurnDeps],
    location: str,
    reason: str = "",
) -> dict[str, Any]:
    """Move the party along an authoritative exit after the fiction supports it."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        destination_id = validate_travel(state, location)
    except ValueError as exc:
        return {"error": str(exc)}

    event = LocationChanged(location=destination_id, reason=reason)
    try:
        await ctx.deps.store.append_event(ctx.deps.session_id, event)
    except KeyError as exc:
        return {"error": str(exc)}
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")


async def take_item(
    ctx: RunContext[TurnDeps],
    item_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Take a portable nearby Item from the current Location into inventory."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        plan = plan_take(state, item_id)
    except ValueError as exc:
        return {"error": str(exc)}

    event = ItemTaken(
        item_id=plan.item_id,
        name=plan.name,
        qty=plan.qty,
        from_location_id=plan.from_location_id,
        consumable=plan.consumable,
        reason=reason,
    )
    try:
        await ctx.deps.store.append_event(ctx.deps.session_id, event)
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")


async def use_item(
    ctx: RunContext[TurnDeps],
    item_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """Validate an available Item; consumables deduct quantity deterministically."""
    state = await ctx.deps.store.get_snapshot(ctx.deps.session_id)
    if state is None:
        return {"error": f"session not found: {ctx.deps.session_id}"}
    try:
        plan = plan_use(state, item_id)
    except ValueError as exc:
        return {"error": str(exc)}

    if not plan.consumable:
        return {
            "ok": True,
            "item_id": plan.item_id,
            "name": plan.name,
            "qty": plan.qty,
            "source": plan.source,
            "consumable": False,
            "reason": reason,
        }

    try:
        consume = plan_consume(state, item_id)
    except ValueError as exc:
        return {"error": str(exc)}

    event = ItemConsumed(
        item_id=consume.item_id,
        qty=consume.qty,
        source=consume.source,
        location_id=consume.location_id,
        reason=reason,
    )
    try:
        await ctx.deps.store.append_event(ctx.deps.session_id, event)
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}
    ctx.deps.events_this_turn.append(event)
    return event.model_dump(mode="json")
