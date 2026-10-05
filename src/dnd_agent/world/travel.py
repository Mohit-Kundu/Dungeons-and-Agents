"""Deterministic travel validation against PlayableWorld exits."""

from __future__ import annotations

import re

from pydantic import BaseModel

from dnd_agent.domain.models import GameState, PlayableWorld, WorldLocation

_TRAVEL_VERBS = re.compile(
    r"\b("
    r"go|goes|going|move|moves|moving|travel|travels|travelling|traveling|"
    r"enter|enters|entering|head|heads|heading|walk|walks|walking|"
    r"proceed|proceeds|follow|follows|following"
    r")\b",
    re.IGNORECASE,
)


class ReachableDestination(BaseModel):
    id: str
    name: str


def _location_map(world: PlayableWorld) -> dict[str, WorldLocation]:
    return {location.id: location for location in world.locations}


def resolve_location_ref(world: PlayableWorld, location: str) -> str | None:
    """Map a Location id or display name onto a stable Location id."""
    text = location.strip()
    if not text:
        return None
    for candidate in world.locations:
        if text == candidate.id or text.casefold() == candidate.name.casefold():
            return candidate.id
    return None


def reachable_destinations(state: GameState) -> list[ReachableDestination]:
    """Return exits from the current Location as authoritative destinations."""
    locations = _location_map(state.world)
    current = locations.get(state.location)
    if current is None:
        return []
    destinations: list[ReachableDestination] = []
    for exit_id in current.exits:
        destination = locations.get(exit_id)
        if destination is None:
            continue
        destinations.append(ReachableDestination(id=destination.id, name=destination.name))
    return destinations


def validate_travel(state: GameState, location: str) -> str:
    """Return the destination Location id, or raise ValueError if travel is illegal."""
    text = location.strip()
    if not text:
        raise ValueError("location must not be empty")

    destination_id = resolve_location_ref(state.world, text)
    if destination_id is None:
        raise ValueError(f"unknown location: {text}")

    if destination_id == state.location:
        raise ValueError(f"already at location: {destination_id}")

    reachable_ids = {destination.id for destination in reachable_destinations(state)}
    if destination_id not in reachable_ids:
        raise ValueError(f"no route from {state.location} to {destination_id}")

    return destination_id


def detect_travel_destination(player_text: str, state: GameState) -> str | None:
    """Return a Location id when player text clearly targets one destination."""
    if not _TRAVEL_VERBS.search(player_text):
        return None

    matches: list[str] = []
    for location in state.world.locations:
        patterns = (
            rf"\b{re.escape(location.id)}\b",
            rf"\b{re.escape(location.name)}\b",
        )
        if any(re.search(pattern, player_text, re.IGNORECASE) for pattern in patterns):
            matches.append(location.id)

    unique = list(dict.fromkeys(matches))
    if len(unique) == 1:
        return unique[0]
    return None


def format_reachable_lines(destinations: list[ReachableDestination]) -> str:
    if not destinations:
        return "- (none)"
    return "\n".join(f"- {destination.id} ({destination.name})" for destination in destinations)


def rejected_travel_narration(
    error: str,
    destinations: list[ReachableDestination],
) -> str:
    choices = format_reachable_lines(destinations)
    return f"You cannot travel that way: {error}. From here you can reach:\n{choices}"
