"""Seam: CLI ApiClient create/state against the HTTP API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dnd_agent.api.app import create_app
from dnd_agent.cli.client import ApiClient
from dnd_agent.store.event_store import EventStore


@pytest.fixture
def api_client(tmp_path: Path):
    store = EventStore(tmp_path / "cli.db")
    app = create_app(store=store)
    with TestClient(app) as test_client:
        yield ApiClient(client=test_client)


def test_cli_client_creates_and_reads_session(api_client: ApiClient) -> None:
    state = api_client.create_session(scenario_id="goblin_cave", rng_seed=5)

    loaded = api_client.get_state(state.session_id)
    events = api_client.list_events(state.session_id)

    assert loaded.character.name == "Brynn Ironfoot"
    assert loaded.location == "Cave Mouth"
    assert loaded.rng_seed == 5
    assert len(events) == 1
    assert events[0].type == "session_created"
