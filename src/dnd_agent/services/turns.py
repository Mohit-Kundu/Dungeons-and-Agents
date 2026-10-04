"""Turn orchestration: load context, run DM Agent, persist narration."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from dnd_agent.agent.deps import TurnDeps
from dnd_agent.agent.dm_agent import build_dm_agent
from dnd_agent.config import Settings, get_settings
from dnd_agent.domain.events import Event
from dnd_agent.domain.models import GameState
from dnd_agent.store.event_store import EventStore


@dataclass(frozen=True)
class TurnResult:
    session_id: str
    turn_number: int
    player_text: str
    narration: str
    state: GameState
    events: list[Event]
    status: str


def _format_context(state: GameState, recent_turns: list[dict]) -> str:
    history_lines: list[str] = []
    for turn in recent_turns:
        history_lines.append(f"Player: {turn['player_text']}")
        history_lines.append(f"DM: {turn['narration']}")
    history = "\n".join(history_lines) if history_lines else "(no prior turns)"
    return (
        f"Current GameState JSON:\n{state.model_dump_json(indent=2)}\n\n"
        f"Recent turns:\n{history}\n\n"
        f"Rolling summary:\n{state.summary or '(empty)'}"
    )


class TurnService:
    def __init__(
        self,
        store: EventStore,
        *,
        settings: Settings | None = None,
        model: Model | str | None = None,
    ) -> None:
        self._store = store
        self._settings = settings or get_settings()
        self._model = model if model is not None else self._settings.model
        self._agent = build_dm_agent(self._model)

    async def run_turn(self, session_id: str, player_text: str) -> TurnResult:
        text = player_text.strip()
        if not text:
            raise ValueError("player_text must not be empty")

        state = await self._store.get_snapshot(session_id)
        if state is None:
            raise KeyError(f"session not found: {session_id}")

        recent = await self._store.list_recent_turns(
            session_id,
            limit=self._settings.memory_recent_turns,
        )
        deps = TurnDeps(store=self._store, session_id=session_id)
        prompt = (
            f"{_format_context(state, recent)}\n\n"
            f"Player action:\n{text}\n\n"
            "Resolve the action. Call tools for any Check or roll before narrating the outcome."
        )

        status = "ok"
        try:
            result = await self._agent.run(
                prompt,
                deps=deps,
                usage_limits=UsageLimits(
                    request_limit=self._settings.max_tool_calls_per_turn + 2,
                    tool_calls_limit=self._settings.max_tool_calls_per_turn,
                ),
            )
            narration = result.output.strip() or "The world holds its breath."
        except Exception as exc:  # noqa: BLE001 - persist aborted Turn
            status = "aborted"
            narration = f"The Turn could not be completed: {exc}"

        turn_number = await self._store.add_turn(
            session_id,
            player_text=text,
            narration=narration,
            status=status,
        )
        fresh_state = await self._store.get_snapshot(session_id)
        assert fresh_state is not None
        return TurnResult(
            session_id=session_id,
            turn_number=turn_number,
            player_text=text,
            narration=narration,
            state=fresh_state,
            events=list(deps.events_this_turn),
            status=status,
        )
