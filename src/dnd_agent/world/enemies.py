"""Deterministic Check-based damage against homogeneous Enemy Groups."""

from __future__ import annotations

from pydantic import BaseModel, Field

from dnd_agent.domain.events import EnemyGroupDamaged, Event, SkillCheckResolved
from dnd_agent.domain.models import EnemyGroup, GameState


class ResolveEnemyPlan(BaseModel):
    enemy_group_id: str
    name: str
    damage: int = Field(ge=1)
    current_hp: int = Field(ge=0)
    max_hp: int = Field(ge=0)
    remaining_count: int = Field(ge=0)
    defeated_count: int = Field(ge=0)


class EnemyStatus(BaseModel):
    """Authoritative Enemy Group health for Turn guidance."""

    id: str
    name: str
    location_id: str
    current_hp: int = Field(ge=0)
    max_hp: int = Field(ge=0)
    remaining_count: int = Field(ge=0)
    defeated_count: int = Field(ge=0)


def enemy_statuses(state: GameState) -> list[EnemyStatus]:
    return [
        EnemyStatus(
            id=group.id,
            name=group.name,
            location_id=group.location_id,
            current_hp=group.current_hp,
            max_hp=group.max_hp,
            remaining_count=group.remaining_count,
            defeated_count=group.defeated_count,
        )
        for group in state.world.enemy_groups
    ]


def format_enemy_status_lines(statuses: list[EnemyStatus]) -> str:
    if not statuses:
        return "- (none)"
    return "\n".join(
        f"- {status.id} ({status.name}) @ {status.location_id}: "
        f"HP {status.current_hp}/{status.max_hp}, "
        f"remaining {status.remaining_count}, defeated {status.defeated_count}"
        for status in statuses
    )


def _find_group(state: GameState, enemy_group_id: str) -> EnemyGroup | None:
    for group in state.world.enemy_groups:
        if group.id == enemy_group_id:
            return group
    return None


def _unused_successful_checks(turn_events: list[Event]) -> int:
    successes = sum(
        1
        for event in turn_events
        if isinstance(event, SkillCheckResolved) and event.success
    )
    damages = sum(1 for event in turn_events if isinstance(event, EnemyGroupDamaged))
    return successes - damages


def plan_resolve_enemy(
    state: GameState,
    enemy_group_id: str,
    *,
    turn_events: list[Event],
) -> ResolveEnemyPlan:
    """Plan Scenario resolution_damage against a present Enemy Group."""
    text = enemy_group_id.strip()
    if not text:
        raise ValueError("enemy_group_id must not be empty")

    group = _find_group(state, text)
    if group is None:
        raise ValueError(f"unknown enemy group: {text}")
    if group.location_id != state.location:
        raise ValueError(f"enemy group not present here: {text}")
    if group.remaining_count <= 0 or group.current_hp <= 0:
        raise ValueError(f"enemy group already defeated: {text}")
    if _unused_successful_checks(turn_events) < 1:
        raise ValueError(
            "enemy resolution requires a successful qualifying Check in this Turn"
        )

    damage = min(group.resolution_damage, group.current_hp)
    after = group.model_copy(update={"current_hp": group.current_hp - damage})
    return ResolveEnemyPlan(
        enemy_group_id=group.id,
        name=group.name,
        damage=damage,
        current_hp=after.current_hp,
        max_hp=after.max_hp,
        remaining_count=after.remaining_count,
        defeated_count=after.defeated_count,
    )
