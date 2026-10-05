"""Rich rendering helpers for Session state and live Turn progress."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table

from dnd_agent.domain.models import GameState

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


def render_state(state: GameState) -> None:
    character = state.character
    sheet = Table(show_header=False, box=None, padding=(0, 1))
    sheet.add_row("Session", state.session_id)
    sheet.add_row("Scenario", state.scenario_id)
    sheet.add_row("Location", state.location)
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
