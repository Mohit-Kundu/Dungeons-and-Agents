"""CLI entry point."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Protocol

import httpx
import typer
import uvicorn

from dnd_agent.api.app import create_app
from dnd_agent.cli.client import ApiClient, ApiError
from dnd_agent.cli.render import (
    TurnProgressDisplay,
    console,
    format_stream_event,
    render_state,
)
from dnd_agent.config import get_settings
from dnd_agent.domain.models import GameState


class ProgressDisplay(Protocol):
    def show(self, label: str) -> None: ...

    def pulse(self) -> None: ...

    def clear(self) -> None: ...

app = typer.Typer(
    name="dnd",
    help="Play a Session with the D&D Agent DM.",
    no_args_is_help=True,
)


def _client() -> ApiClient:
    settings = get_settings()
    return ApiClient(settings.api_base_url)


def _with_api[T](action: Callable[[ApiClient], T], *, hint_serve: bool = False) -> T:
    try:
        with _client() as client:
            return action(client)
    except ApiError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]Could not reach API at {get_settings().api_base_url}: {exc}[/red]")
        if hint_serve:
            console.print("Start the server with: [bold]dnd serve[/bold]")
        raise typer.Exit(code=1) from exc


def consume_turn_stream(
    events: Iterator[dict[str, Any]],
    *,
    progress: ProgressDisplay | None = None,
) -> GameState | None:
    """Render a live Turn stream with animated waits and permanent reveals."""
    display: ProgressDisplay = progress or TurnProgressDisplay()
    final_state: GameState | None = None
    narration_started = False
    try:
        display.show("The DM considers your move")
        for event in events:
            event_type = event.get("type")
            if event_type == "progress":
                label = str(event.get("label") or "The DM considers your move")
                display.show(label)
                continue
            if event_type == "tool_call":
                # Progress events carry the player-facing copy; keep the spinner alive.
                display.pulse()
                continue
            if event_type == "narration_delta":
                text = str(event.get("text", ""))
                if not narration_started:
                    display.clear()
                    narration_started = True
                    console.print()
                console.print(text, end="")
                continue

            display.clear()
            if narration_started:
                console.print()
                narration_started = False
            line = format_stream_event(event)
            if line:
                console.print(line)
                if event_type == "roll":
                    console.print()
            if event_type == "done":
                final_state = GameState.model_validate(event["state"])
            elif event_type == "error":
                continue
            else:
                # Resume anticipation until the next reveal or narration.
                display.show("The DM weaves the outcome")
        if narration_started:
            console.print()
    finally:
        display.clear()
    return final_state


@app.command("serve")
def serve(
    host: str | None = typer.Option(None, help="Bind host"),
    port: int | None = typer.Option(None, help="Bind port"),
) -> None:
    """Start the FastAPI server."""
    settings = get_settings()
    uvicorn.run(
        create_app(settings=settings),
        host=host or settings.api_host,
        port=port or settings.api_port,
    )


@app.command("new")
def new_session(
    scenario: str = typer.Option("goblin_cave", "--scenario", "-s"),
    seed: int | None = typer.Option(None, "--seed", help="RNG seed"),
) -> None:
    """Create a Session from the starter scenario."""
    state = _with_api(
        lambda client: client.create_session(scenario_id=scenario, rng_seed=seed),
        hint_serve=True,
    )
    console.print(f"[green]Created Session[/green] {state.session_id}")
    if state.summary.strip():
        console.print()
        console.print(state.summary.strip())
        console.print()
    render_state(state)


@app.command("state")
def show_state(session_id: str = typer.Argument(..., help="Session id")) -> None:
    """Show the current Snapshot for a Session."""
    state = _with_api(lambda client: client.get_state(session_id))
    render_state(state)


@app.command("log")
def show_log(session_id: str = typer.Argument(..., help="Session id")) -> None:
    """List Events for a Session."""
    events = _with_api(lambda client: client.list_events(session_id))
    for index, event in enumerate(events, start=1):
        console.print(f"{index}. [cyan]{event.type}[/cyan]")


@app.command("play")
def play_turn(
    session_id: str = typer.Argument(..., help="Session id"),
    action: str = typer.Argument(..., help="Player action text"),
) -> None:
    """Play one Turn: stream narration and mechanical Events over SSE."""

    def _consume(client: ApiClient) -> GameState | None:
        return consume_turn_stream(client.play_turn(session_id, action))

    state = _with_api(_consume, hint_serve=True)
    if state is not None:
        render_state(state)


if __name__ == "__main__":
    app()
