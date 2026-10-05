"""Seam: goblin_cave scenario ships with intro, locations, and beats."""

from __future__ import annotations

from dnd_agent.content.loader import load_scenario


def test_goblin_cave_briefing_includes_intro_locations_and_beats() -> None:
    scenario = load_scenario("goblin_cave")
    briefing = scenario.briefing()
    assert "Cave Mouth" in briefing
    assert "Goblin Den" in briefing
    assert "Suggested beats" in briefing
    assert "Authoritative Playable Facts" in briefing
