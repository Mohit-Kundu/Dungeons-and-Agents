"""Seam: CLI renders authoritative reachable destinations."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from dnd_agent.cli import render as render_mod
from dnd_agent.cli.render import format_reachable_destinations, render_state
from dnd_agent.content.loader import load_scenario
from dnd_agent.domain.models import (
    AbilityScores,
    Character,
    GameState,
    Quest,
)
from dnd_agent.world.travel import ReachableDestination


def test_format_reachable_destinations() -> None:
    text = format_reachable_destinations(
        [
            ReachableDestination(id="twisting_tunnel", name="Twisting Tunnel"),
            ReachableDestination(id="goblin_den", name="Goblin Den"),
        ]
    )
    assert "Twisting Tunnel [twisting_tunnel]" in text
    assert "Goblin Den [goblin_den]" in text


def test_render_state_includes_reachable_row() -> None:
    scenario = load_scenario("goblin_cave")
    state = GameState(
        session_id="sess_1",
        scenario_id="goblin_cave",
        character=Character(
            id="pregen_fighter",
            name="Brynn",
            level=1,
            class_name="Fighter",
            abilities=AbilityScores(
                strength=16,
                dexterity=12,
                constitution=14,
                intelligence=10,
                wisdom=11,
                charisma=13,
            ),
            proficiency_bonus=2,
            max_hp=12,
            hp=12,
            hit_die=10,
            hit_dice_total=1,
            hit_dice_remaining=1,
            armor_class=16,
        ),
        location="cave_mouth",
        quest=Quest(
            id="clear_cave",
            title="Clear the Cave",
            summary="Clear it.",
            status="active",
        ),
        rng_seed=1,
        world=scenario.build_world(current_location_id="cave_mouth"),
    )

    buffer = StringIO()
    original = render_mod.console
    render_mod.console = Console(file=buffer, force_terminal=False, width=120)
    try:
        render_state(state)
        output = buffer.getvalue()
    finally:
        render_mod.console = original

    assert "Reachable" in output
    assert "Twisting Tunnel" in output
