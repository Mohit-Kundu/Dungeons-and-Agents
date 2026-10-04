"""Rich rendering helpers for Session state."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dnd_agent.domain.models import GameState

console = Console()


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
    sheet.add_row("AC", str(character.armor_class))
    sheet.add_row(
        "Conditions",
        ", ".join(character.conditions) if character.conditions else "none",
    )
    inventory = ", ".join(f"{item.name}×{item.qty}" for item in character.inventory) or "empty"
    sheet.add_row("Inventory", inventory)

    console.print(Panel(sheet, title="GameState", border_style="cyan"))
