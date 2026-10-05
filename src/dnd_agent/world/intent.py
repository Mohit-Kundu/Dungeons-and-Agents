"""Fail-closed Action Intent models and validation against Playable Facts."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from dnd_agent.domain.models import GameState, WorldLocation
from dnd_agent.world.travel import reachable_destinations, validate_travel

ActionKind = Literal["use", "interact", "resolve_enemy", "travel", "general"]
Confidence = Literal["high", "low"]


class ProposedActionIntent(BaseModel):
    """Model-proposed interpretation of a player action before code validation."""

    kind: ActionKind
    confidence: Confidence = "high"
    ambiguous: bool = False
    item_ids: list[str] = Field(default_factory=list)
    interactable_ids: list[str] = Field(default_factory=list)
    enemy_group_ids: list[str] = Field(default_factory=list)
    destination_id: str | None = None
    note: str = ""


class ValidatedActionIntent(BaseModel):
    """Authoritative Action Intent after Playable Fact validation."""

    kind: ActionKind
    item_ids: list[str] = Field(default_factory=list)
    interactable_ids: list[str] = Field(default_factory=list)
    enemy_group_ids: list[str] = Field(default_factory=list)
    destination_id: str | None = None


class IntentValidationResult(BaseModel):
    ok: bool
    reason: str = ""
    intent: ValidatedActionIntent | None = None


class IntentProposer(Protocol):
    async def propose(self, player_text: str, state: GameState) -> ProposedActionIntent: ...


def _current_location(state: GameState) -> WorldLocation | None:
    for location in state.world.locations:
        if location.id == state.location:
            return location
    return None


def available_item_ids(state: GameState) -> set[str]:
    ids = {item.id for item in state.character.inventory}
    current = _current_location(state)
    if current is not None:
        ids.update(item.id for item in current.items)
    return ids


def available_interactable_ids(state: GameState) -> set[str]:
    current = _current_location(state)
    if current is None:
        return set()
    return {item.id for item in current.interactables}


def available_enemy_group_ids(state: GameState) -> set[str]:
    return {
        group.id
        for group in state.world.enemy_groups
        if group.location_id == state.location and group.remaining_count > 0
    }


def catalog_playable_facts(state: GameState) -> dict[str, list[str]]:
    """Compact catalog of IDs the intent model may reference."""
    current = _current_location(state)
    return {
        "inventory_item_ids": [item.id for item in state.character.inventory],
        "location_item_ids": [item.id for item in current.items] if current else [],
        "interactable_ids": sorted(available_interactable_ids(state)),
        "enemy_group_ids": sorted(available_enemy_group_ids(state)),
        "reachable_destination_ids": [
            destination.id for destination in reachable_destinations(state)
        ],
        "all_location_ids": [location.id for location in state.world.locations],
    }


def validate_action_intent(
    state: GameState,
    proposed: ProposedActionIntent,
) -> IntentValidationResult:
    """Fail closed: only allow Playable Facts present for the chosen Action Intent kind."""
    if proposed.confidence != "high":
        return IntentValidationResult(
            ok=False,
            reason="uncertain Action Intent: confidence is too low to act safely",
        )
    if proposed.ambiguous:
        return IntentValidationResult(
            ok=False,
            reason="ambiguous Action Intent: clarify which Playable Fact you mean",
        )

    if proposed.kind == "general":
        if (
            proposed.item_ids
            or proposed.interactable_ids
            or proposed.enemy_group_ids
            or proposed.destination_id
        ):
            return IntentValidationResult(
                ok=False,
                reason="general Action Intent must not target specific Playable Facts",
            )
        return IntentValidationResult(
            ok=True,
            intent=ValidatedActionIntent(kind="general"),
        )

    if proposed.kind == "use":
        if not proposed.item_ids:
            return IntentValidationResult(
                ok=False,
                reason="use Action Intent requires an item id",
            )
        available = available_item_ids(state)
        for item_id in proposed.item_ids:
            if item_id not in available:
                known = {
                    item.id for location in state.world.locations for item in location.items
                } | {item.id for item in state.character.inventory}
                if item_id not in known:
                    return IntentValidationResult(
                        ok=False,
                        reason=f"unknown item: {item_id}",
                    )
                return IntentValidationResult(
                    ok=False,
                    reason=f"unavailable item: {item_id}",
                )
        return IntentValidationResult(
            ok=True,
            intent=ValidatedActionIntent(kind="use", item_ids=list(proposed.item_ids)),
        )

    if proposed.kind == "interact":
        if not proposed.interactable_ids:
            return IntentValidationResult(
                ok=False,
                reason="interact Action Intent requires an interactable id",
            )
        available = available_interactable_ids(state)
        known = {
            interactable.id
            for location in state.world.locations
            for interactable in location.interactables
        }
        for interactable_id in proposed.interactable_ids:
            if interactable_id not in known:
                return IntentValidationResult(
                    ok=False,
                    reason=f"unknown interactable: {interactable_id}",
                )
            if interactable_id not in available:
                return IntentValidationResult(
                    ok=False,
                    reason=f"interactable not present here: {interactable_id}",
                )
        return IntentValidationResult(
            ok=True,
            intent=ValidatedActionIntent(
                kind="interact",
                interactable_ids=list(proposed.interactable_ids),
            ),
        )

    if proposed.kind == "resolve_enemy":
        if not proposed.enemy_group_ids:
            return IntentValidationResult(
                ok=False,
                reason="resolve_enemy Action Intent requires an enemy group id",
            )
        available = available_enemy_group_ids(state)
        known = {group.id for group in state.world.enemy_groups}
        for enemy_group_id in proposed.enemy_group_ids:
            if enemy_group_id not in known:
                return IntentValidationResult(
                    ok=False,
                    reason=f"unknown enemy group: {enemy_group_id}",
                )
            if enemy_group_id not in available:
                return IntentValidationResult(
                    ok=False,
                    reason=f"enemy group not present here: {enemy_group_id}",
                )
        return IntentValidationResult(
            ok=True,
            intent=ValidatedActionIntent(
                kind="resolve_enemy",
                enemy_group_ids=list(proposed.enemy_group_ids),
            ),
        )

    # travel
    if not proposed.destination_id:
        return IntentValidationResult(
            ok=False,
            reason="travel Action Intent requires a destination id",
        )
    try:
        destination_id = validate_travel(state, proposed.destination_id)
    except ValueError as exc:
        return IntentValidationResult(ok=False, reason=str(exc))
    return IntentValidationResult(
        ok=True,
        intent=ValidatedActionIntent(kind="travel", destination_id=destination_id),
    )


def format_validated_intent(intent: ValidatedActionIntent) -> str:
    lines = [f"kind: {intent.kind}"]
    if intent.item_ids:
        lines.append(f"item_ids: {', '.join(intent.item_ids)}")
    if intent.interactable_ids:
        lines.append(f"interactable_ids: {', '.join(intent.interactable_ids)}")
    if intent.enemy_group_ids:
        lines.append(f"enemy_group_ids: {', '.join(intent.enemy_group_ids)}")
    if intent.destination_id:
        lines.append(f"destination_id: {intent.destination_id}")
    return "\n".join(lines)


def rejected_intent_narration(reason: str) -> str:
    return (
        f"You cannot do that: {reason}. "
        "Only inventory items, nearby surroundings, present enemies, "
        "and Reachable Destinations may be targeted."
    )


INTENT_SYSTEM_PROMPT = """
You classify a solo D&D player's free-text action into a structured Action Intent.

Rules:
- Choose kind: use, interact, resolve_enemy, travel, or general.
- Only reference ids from the provided Playable Fact catalog.
- If the player clearly targets one allowed fact, set confidence=high.
- If the target is unclear or could be more than one fact, set ambiguous=true and confidence=low.
- If you cannot tell what they mean, set confidence=low.
- general actions (listen, wait, look around) use kind=general with no target ids.
- Output only the structured Action Intent fields.
""".strip()


class CodeIntentService:
    """Deterministic proposer: travel detection, otherwise general."""

    async def propose(self, player_text: str, state: GameState) -> ProposedActionIntent:
        from dnd_agent.world.travel import detect_travel_destination

        destination = detect_travel_destination(player_text, state)
        if destination is not None:
            return ProposedActionIntent(
                kind="travel",
                destination_id=destination,
                confidence="high",
            )
        return ProposedActionIntent(kind="general", confidence="high")


class IntentService:
    """LLM proposer that returns a ProposedActionIntent from cataloged Playable Facts."""

    def __init__(self, model: object, *, retries: int = 1) -> None:
        from pydantic_ai import Agent

        self._agent: Agent[None, ProposedActionIntent] = Agent(
            model,  # type: ignore[arg-type]
            output_type=ProposedActionIntent,
            system_prompt=INTENT_SYSTEM_PROMPT,
            retries=retries,
        )

    async def propose(self, player_text: str, state: GameState) -> ProposedActionIntent:
        catalog = catalog_playable_facts(state)
        prompt = (
            f"Playable Fact catalog JSON:\n{catalog}\n\n"
            f"Current location id: {state.location}\n\n"
            f"Player action:\n{player_text.strip()}\n\n"
            "Classify the Action Intent."
        )
        result = await self._agent.run(prompt)
        return result.output
