"""Rich rendering helpers for Session state."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dnd_agent.domain.models import GameState

console = Console()


def format_turn_event(event: dict[str, Any]) -> str:
    """Format one Turn Event dict for CLI display."""
    event_type = event.get("type")
    if event_type == "skill_check_resolved":
        outcome = "success" if event.get("success") else "failure"
        return (
            f"[yellow]Check[/yellow] {event.get('skill')} "
            f"d20={event.get('d20')} mod={event.get('modifier')} "
            f"total={event.get('total')} vs DC {event.get('dc')} → {outcome}"
        )
    if event_type == "saving_throw_resolved":
        outcome = "success" if event.get("success") else "failure"
        return (
            f"[yellow]Save[/yellow] {event.get('ability')} "
            f"d20={event.get('d20')} mod={event.get('modifier')} "
            f"total={event.get('total')} vs DC {event.get('dc')} → {outcome}"
        )
    if event_type == "condition_added":
        return f"[yellow]Condition[/yellow] +{event.get('condition')} ({event.get('reason')})"
    if event_type == "condition_removed":
        return f"[yellow]Condition[/yellow] -{event.get('condition')} ({event.get('reason')})"
    if event_type == "short_rest_completed":
        return (
            f"[yellow]Short rest[/yellow] spent {event.get('hit_dice_spent')} hit dice "
            f"rolls={event.get('hit_dice_rolls')} recovered {event.get('hp_recovered')} HP "
            f"→ {event.get('hp_after')} HP, {event.get('hit_dice_remaining')} hit dice left"
        )
    if event_type == "long_rest_completed":
        cleared = event.get("conditions_cleared") or []
        cleared_text = ", ".join(cleared) if cleared else "none"
        return (
            f"[yellow]Long rest[/yellow] HP→{event.get('hp_after')} "
            f"restored {event.get('hit_dice_restored')} hit dice "
            f"({event.get('hit_dice_remaining')} left); cleared [{cleared_text}]"
        )
    if event_type == "dice_rolled":
        return (
            f"[yellow]Roll[/yellow] {event.get('expression')} = {event.get('total')} "
            f"({event.get('reason')})"
        )
    if event_type == "location_changed":
        return f"[yellow]Location[/yellow] → {event.get('location')}"
    return f"[yellow]Event[/yellow] {event_type}"


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
