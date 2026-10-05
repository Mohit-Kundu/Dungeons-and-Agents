"""Seam: CLI Recap rendering for restore/command refresh."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from dnd_agent.cli import render as render_mod
from dnd_agent.cli.render import render_recap


def test_render_recap_shows_updated_banner_and_text() -> None:
    buffer = StringIO()
    render_mod.console = Console(file=buffer, force_terminal=True, width=80)
    try:
        render_recap("Brynn found tracks at the cave mouth.", refreshed=True)
    finally:
        render_mod.console = Console()

    text = buffer.getvalue()
    assert "Recap updated" in text
    assert "Brynn found tracks" in text


def test_render_recap_failure_preserves_last_good() -> None:
    buffer = StringIO()
    render_mod.console = Console(file=buffer, force_terminal=True, width=80)
    try:
        render_recap("Prior recap text.", failed=True)
    finally:
        render_mod.console = Console()

    text = buffer.getvalue()
    assert "last good Recap" in text
    assert "Prior recap text." in text
