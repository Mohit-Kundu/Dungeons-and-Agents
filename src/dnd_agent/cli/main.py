"""CLI entry point. Commands land in later tickets."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="dnd",
    help="Play a session with the D&D Agent DM.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """D&D Agent command-line interface."""


if __name__ == "__main__":
    app()
