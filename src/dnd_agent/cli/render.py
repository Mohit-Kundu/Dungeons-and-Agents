"""Rich rendering helpers for Session state and live Turn progress."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table

from dnd_agent.api.schemas import LatestTurn, SessionOverviewResponse
from dnd_agent.domain.models import GameState
from dnd_agent.world.enemies import EnemyStatus, enemy_statuses
from dnd_agent.world.objectives import IncompleteObjective, incomplete_objectives
from dnd_agent.world.travel import ReachableDestination, reachable_destinations

console = Console()


def progress_status_text(label: str, tick: int) -> str:
    """Cycle trailing ellipsis so waits feel alive."""
    dots = "." * ((tick % 3) + 1)
    base = label.rstrip(".").rstrip()
    return f"{base}{dots}"


def format_stream_event(event: dict[str, Any]) -> str | None:
    """Format one SSE Turn stream payload. Returns None for status-only / narration."""
    event_type = event.get("type")
    if event_type in {"narration_delta", "progress", "tool_call"}:
        return None
    if event_type == "roll":
        inner = event.get("event") or {}
        return format_turn_event(inner if isinstance(inner, dict) else {})
    if event_type == "state_changed":
        inner = event.get("event") or {}
        return format_turn_event(inner if isinstance(inner, dict) else {})
    if event_type == "error":
        return f"[red]Error[/red] {event.get('message')}"
    if event_type == "done":
        return f"[bold]Turn {event.get('turn_number')}[/bold] ({event.get('status')})"
    return f"[yellow]Stream[/yellow] {event_type}"


def format_reachable_destinations(
    destinations: list[ReachableDestination] | list[dict[str, Any]],
) -> str:
    if not destinations:
        return "(none)"
    lines: list[str] = []
    for destination in destinations:
        if isinstance(destination, ReachableDestination):
            lines.append(f"{destination.name} [{destination.id}]")
        else:
            name = str(destination.get("name") or destination.get("id") or "?")
            dest_id = str(destination.get("id") or "?")
            lines.append(f"{name} [{dest_id}]")
    return ", ".join(lines)


def format_incomplete_objectives(
    objectives: list[IncompleteObjective] | list[dict[str, Any]],
) -> str:
    if not objectives:
        return "(none)"
    lines: list[str] = []
    for item in objectives:
        if isinstance(item, IncompleteObjective):
            lines.append(f"{item.title} [{item.id}]")
        else:
            title = str(item.get("title") or item.get("id") or "?")
            obj_id = str(item.get("id") or "?")
            lines.append(f"{title} [{obj_id}]")
    return ", ".join(lines)


def format_enemy_statuses(
    statuses: list[EnemyStatus] | list[dict[str, Any]],
) -> str:
    if not statuses:
        return "(none)"
    lines: list[str] = []
    for status in statuses:
        if isinstance(status, EnemyStatus):
            lines.append(
                f"{status.name} [{status.id}] "
                f"HP {status.current_hp}/{status.max_hp} "
                f"({status.remaining_count} left)"
            )
        else:
            name = str(status.get("name") or status.get("id") or "?")
            enemy_id = str(status.get("id") or "?")
            current = status.get("current_hp")
            max_hp = status.get("max_hp")
            remaining = status.get("remaining_count")
            lines.append(f"{name} [{enemy_id}] HP {current}/{max_hp} ({remaining} left)")
    return "; ".join(lines)


def format_turn_event(event: dict[str, Any]) -> str:
    """Format one domain Event dict for CLI display."""
    event_type = event.get("type")
    if event_type == "skill_check_resolved":
        skill = str(event.get("skill") or "check").replace("_", " ").title()
        outcome = "SUCCESS" if event.get("success") else "FAILURE"
        tone = "bold green" if event.get("success") else "bold red"
        return (
            f"[bold yellow]◆ {skill} check[/bold yellow]\n"
            f"  d20 {event.get('d20')} + {event.get('modifier')} "
            f"= [bold]{event.get('total')}[/bold]  vs  DC {event.get('dc')}\n"
            f"  [{tone}]{outcome}[/{tone}]"
        )
    if event_type == "saving_throw_resolved":
        ability = str(event.get("ability") or "ability").replace("_", " ").title()
        outcome = "SUCCESS" if event.get("success") else "FAILURE"
        tone = "bold green" if event.get("success") else "bold red"
        return (
            f"[bold yellow]◆ {ability} save[/bold yellow]\n"
            f"  d20 {event.get('d20')} + {event.get('modifier')} "
            f"= [bold]{event.get('total')}[/bold]  vs  DC {event.get('dc')}\n"
            f"  [{tone}]{outcome}[/{tone}]"
        )
    if event_type == "condition_added":
        return f"[yellow]Condition[/yellow] +{event.get('condition')} ({event.get('reason')})"
    if event_type == "condition_removed":
        return f"[yellow]Condition[/yellow] -{event.get('condition')} ({event.get('reason')})"
    if event_type == "short_rest_completed":
        return (
            f"[bold yellow]◆ Short rest[/bold yellow]\n"
            f"  spent {event.get('hit_dice_spent')} hit dice "
            f"rolls={event.get('hit_dice_rolls')} recovered {event.get('hp_recovered')} HP\n"
            f"  → {event.get('hp_after')} HP, {event.get('hit_dice_remaining')} hit dice left"
        )
    if event_type == "long_rest_completed":
        cleared = event.get("conditions_cleared") or []
        cleared_text = ", ".join(cleared) if cleared else "none"
        return (
            f"[bold yellow]◆ Long rest[/bold yellow]\n"
            f"  HP→{event.get('hp_after')}; restored {event.get('hit_dice_restored')} hit dice "
            f"({event.get('hit_dice_remaining')} left)\n"
            f"  cleared [{cleared_text}]"
        )
    if event_type == "dice_rolled":
        reason = event.get("reason") or "fortune"
        return (
            f"[bold yellow]◆ Dice[/bold yellow] {event.get('expression')} "
            f"= [bold]{event.get('total')}[/bold]  ({reason})"
        )
    if event_type == "location_changed":
        return f"[yellow]Location[/yellow] → {event.get('location')}"
    if event_type == "enemy_group_damaged":
        return (
            f"[yellow]Enemy[/yellow] {event.get('enemy_group_id')} "
            f"-{event.get('damage')} HP → {event.get('current_hp')}"
        )
    if event_type == "objective_completed":
        title = event.get("title") or event.get("objective_id")
        return f"[green]Objective[/green] complete: {title}"
    if event_type == "quest_completed":
        title = event.get("title") or event.get("quest_id")
        return f"[bold green]Quest[/bold green] complete: {title}"
    return f"[yellow]Event[/yellow] {event_type}"


class TurnProgressDisplay:
    """Animated wait indicator that clears cleanly before permanent output."""

    def __init__(self, target: Console | None = None) -> None:
        self._console = target or console
        self._status: Status | None = None
        self._label = "The DM considers your move"
        self._tick = 0

    def show(self, label: str) -> None:
        self._label = label.rstrip(".").rstrip() or "The DM considers your move"
        text = progress_status_text(self._label, self._tick)
        if self._status is None:
            self._status = self._console.status(
                f"[dim italic]{text}[/dim italic]",
                spinner="dots",
            )
            self._status.start()
        else:
            self._status.update(f"[dim italic]{text}[/dim italic]")

    def pulse(self) -> None:
        """Advance ellipsis while still waiting on the same phase."""
        if self._status is None:
            return
        self._tick += 1
        self._status.update(
            f"[dim italic]{progress_status_text(self._label, self._tick)}[/dim italic]"
        )

    def clear(self) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None


def format_latest_turn(turn: LatestTurn) -> str:
    return (
        f"[bold]Latest Turn {turn.turn_number}[/bold] ({turn.status})\n"
        f"[cyan]You:[/cyan] {turn.player_text}\n"
        f"[magenta]DM:[/magenta] {turn.narration}"
    )


def render_overview(overview: SessionOverviewResponse) -> None:
    """Show Recap + latest exchange before the GameState panel."""
    recap = overview.state.summary.strip()
    if recap:
        console.print(Panel(recap, title="Recap", border_style="yellow"))
    if overview.latest_turn is not None:
        console.print(
            Panel(
                format_latest_turn(overview.latest_turn),
                title="Last thing that happened",
                border_style="green",
            )
        )
    render_state(overview.state)


def render_state(state: GameState) -> None:
    character = state.character
    sheet = Table(show_header=False, box=None, padding=(0, 1))
    sheet.add_row("Session", state.session_id)
    sheet.add_row("Scenario", state.scenario_id)
    sheet.add_row("Location", state.location)
    sheet.add_row(
        "Reachable",
        format_reachable_destinations(reachable_destinations(state)),
    )
    sheet.add_row(
        "Objectives",
        format_incomplete_objectives(incomplete_objectives(state)),
    )
    sheet.add_row("Enemies", format_enemy_statuses(enemy_statuses(state)))
    sheet.add_row("Quest", f"{state.quest.title} [{state.quest.status}]")
    sheet.add_row(
        "Character",
        f"{character.name} (lvl {character.level} {character.class_name})",
    )
    sheet.add_row("HP", f"{character.hp}/{character.max_hp}")
    sheet.add_row(
        "Hit dice",
        f"{character.hit_dice_remaining}/{character.hit_dice_total} (d{character.hit_die})",
    )
    sheet.add_row("AC", str(character.armor_class))
    sheet.add_row(
        "Conditions",
        ", ".join(character.conditions) if character.conditions else "none",
    )
    inventory = ", ".join(f"{item.name}×{item.qty}" for item in character.inventory) or "empty"
    sheet.add_row("Inventory", inventory)

    console.print(Panel(sheet, title="GameState", border_style="cyan"))
