"""CLI entry point."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import typer
import uvicorn

from dnd_agent.api.app import create_app
from dnd_agent.cli.client import ApiClient, ApiError
from dnd_agent.cli.render import console, format_stream_event, render_state
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
    """Play one Turn: stream narration and mechanical Events over SSE."""

    def _consume(client: ApiClient) -> GameState | None:
        final_state: GameState | None = None
        narration_started = False
        for event in client.play_turn(session_id, action):
            event_type = event.get("type")
            if event_type == "narration_delta":
                text = str(event.get("text", ""))
                if not narration_started:
                    narration_started = True
                console.print(text, end="")
            else:
                if narration_started and event_type != "narration_delta":
                    console.print()
                    narration_started = False
                line = format_stream_event(event)
                if line:
                    console.print(line)
            if event_type == "done":
                final_state = GameState.model_validate(event["state"])
        if narration_started:
            console.print()
        return final_state

    state = _with_api(_consume, hint_serve=True)
    if state is not None:
        render_state(state)


if __name__ == "__main__":
    app()
