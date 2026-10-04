"""HTTP client used by the CLI to talk to the API."""

from __future__ import annotations

from typing import Any

import httpx

from dnd_agent.domain.events import EVENT_ADAPTER, Event
from dnd_agent.domain.models import GameState


class ApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


class ApiClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        client: httpx.Client | Any | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def create_session(
        self,
        *,
        scenario_id: str = "goblin_cave",
        character_id: str | None = None,
        rng_seed: int | None = None,
    ) -> GameState:
        payload: dict[str, Any] = {"scenario_id": scenario_id}
        if character_id is not None:
            payload["character_id"] = character_id
        if rng_seed is not None:
            payload["rng_seed"] = rng_seed
        response = self._client.post("/sessions", json=payload)
        self._raise_for_status(response)
        return GameState.model_validate(response.json())

    def get_state(self, session_id: str) -> GameState:
        response = self._client.get(f"/sessions/{session_id}/state")
        self._raise_for_status(response)
        return GameState.model_validate(response.json())

    def list_events(self, session_id: str) -> list[Event]:
        response = self._client.get(f"/sessions/{session_id}/events")
        self._raise_for_status(response)
        raw_events = response.json()["events"]
        return [EVENT_ADAPTER.validate_python(item) for item in raw_events]

    def play_turn(self, session_id: str, player_text: str) -> dict[str, Any]:
        response = self._client.post(
            f"/sessions/{session_id}/turns",
            json={"player_text": player_text},
            timeout=120.0,
        )
        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            body = response.json()
            detail = str(body.get("detail", body))
        except Exception:
            detail = response.text
        raise ApiError(response.status_code, detail)
