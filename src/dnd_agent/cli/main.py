"""CLI entry point."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import typer
import uvicorn

from dnd_agent.api.app import create_app
from dnd_agent.cli.client import ApiClient, ApiError
from dnd_agent.cli.render import console, render_state
from dnd_agent.config import get_settings
from dnd_agent.domain.models import GameState

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
    """Play one Turn: send an action, print narration and mechanical Events."""
    result = _with_api(
        lambda client: client.play_turn(session_id, action),
        hint_serve=True,
    )
    console.print(f"[bold]Turn {result['turn_number']}[/bold] ({result['status']})")
    console.print(result["narration"])
    for event in result.get("events", []):
        event_type = event.get("type")
        if event_type == "skill_check_resolved":
            outcome = "success" if event.get("success") else "failure"
            console.print(
                f"[yellow]Check[/yellow] {event.get('skill')} "
                f"d20={event.get('d20')} mod={event.get('modifier')} "
                f"total={event.get('total')} vs DC {event.get('dc')} → {outcome}"
            )
        elif event_type == "dice_rolled":
            console.print(
                f"[yellow]Roll[/yellow] {event.get('expression')} = {event.get('total')} "
                f"({event.get('reason')})"
            )
        elif event_type == "location_changed":
            console.print(f"[yellow]Location[/yellow] → {event.get('location')}")
    render_state(GameState.model_validate(result["state"]))


if __name__ == "__main__":
    app()
