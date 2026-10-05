"""Deterministic Objective and Quest completion from PlayableWorld predicates."""

from __future__ import annotations

from pydantic import BaseModel

from dnd_agent.domain.events import Event, ObjectiveCompleted, QuestCompleted
from dnd_agent.domain.models import (
    EnemiesDefeatedPredicate,
    GameState,
    InventoryContainsPredicate,
    LocationVisitedPredicate,
    Objective,
    ObjectivePredicate,
)


class IncompleteObjective(BaseModel):
    id: str
    title: str
    summary: str = ""


def predicate_satisfied(state: GameState, predicate: ObjectivePredicate) -> bool:
    """Return whether an Objective predicate holds for the current Snapshot."""
    if isinstance(predicate, LocationVisitedPredicate):
        return predicate.location_id in state.world.visited_location_ids
    if isinstance(predicate, InventoryContainsPredicate):
        needed = predicate.qty
        have = sum(
            item.qty for item in state.character.inventory if item.id == predicate.item_id
        )
        return have >= needed
    if isinstance(predicate, EnemiesDefeatedPredicate):
        for group in state.world.enemy_groups:
            if group.id == predicate.enemy_group_id:
                return group.remaining_count <= 0
        return False
    raise TypeError(f"unsupported objective predicate: {type(predicate)!r}")


def incomplete_objectives(state: GameState) -> list[IncompleteObjective]:
    """Active Objectives the player still needs to finish."""
    return [
        IncompleteObjective(id=objective.id, title=objective.title, summary=objective.summary)
        for objective in state.world.objectives
        if objective.status == "active"
    ]


def _newly_completed(state: GameState) -> list[Objective]:
    completed: list[Objective] = []
    for objective in state.world.objectives:
        if objective.status != "active":
            continue
        if predicate_satisfied(state, objective.predicate):
            completed.append(objective)
    return completed


def plan_progress_events(state: GameState) -> list[Event]:
    """Emit ObjectiveCompleted / QuestCompleted Events for newly satisfied work."""
    events: list[Event] = []
    newly_done_ids = {objective.id for objective in _newly_completed(state)}
    for objective in state.world.objectives:
        if objective.id in newly_done_ids:
            events.append(
                ObjectiveCompleted(
                    objective_id=objective.id,
                    title=objective.title,
                    reason="predicate_satisfied",
                )
            )

    if state.quest.status != "active":
        return events

    remaining_active = [
        objective
        for objective in state.world.objectives
        if objective.status == "active" and objective.id not in newly_done_ids
    ]
    if not remaining_active and state.world.objectives:
        events.append(
            QuestCompleted(
                quest_id=state.quest.id,
                title=state.quest.title,
                reason="all_objectives_complete",
            )
        )
    return events


def format_incomplete_objective_lines(objectives: list[IncompleteObjective]) -> str:
    if not objectives:
        return "- (none)"
    return "\n".join(
        f"- {item.id}: {item.title}"
        + (f" — {item.summary}" if item.summary else "")
        for item in objectives
    )
