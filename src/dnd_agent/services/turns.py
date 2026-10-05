"""Turn orchestration: load context, run DM Agent, persist narration."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.models import Model
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.usage import UsageLimits

from dnd_agent.agent.deps import TurnDeps
from dnd_agent.agent.dm_agent import build_dm_agent
from dnd_agent.agent.providers import resolve_model
from dnd_agent.config import Settings, get_settings
from dnd_agent.domain.events import Event
from dnd_agent.domain.models import GameState
from dnd_agent.services.session_locks import SessionLockRegistry
from dnd_agent.services.stream_events import (
    ROLL_EVENT_TYPES,
    STATE_EVENT_TYPES,
    DoneEvent,
    ErrorEvent,
    NarrationDelta,
    ProgressEvent,
    RollEvent,
    StateChangedEvent,
    ToolCallEvent,
    TurnStreamEvent,
)
from dnd_agent.store.event_store import EventStore
from dnd_agent.world.enemies import EnemyStatus, enemy_statuses, format_enemy_status_lines
from dnd_agent.world.intent import (
    CodeIntentService,
    IntentProposer,
    ValidatedActionIntent,
    format_validated_intent,
    rejected_intent_narration,
    validate_action_intent,
)
from dnd_agent.world.objectives import (
    IncompleteObjective,
    format_incomplete_objective_lines,
    incomplete_objectives,
    plan_progress_events,
)
from dnd_agent.world.travel import (
    ReachableDestination,
    format_reachable_lines,
    reachable_destinations,
)
ROLLING_TOOLS = frozenset({"skill_check", "saving_throw", "roll_dice", "short_rest"})

_AWAITING_OPENERS = (
    "The DM considers your move",
    "Torchlight flickers across the screen",
    "Something stirs behind the DM's screen",
)
_AWAITING_AFTER_ROLL = (
    "The DM weaves the outcome",
    "The dice have spoken — the story turns",
    "The world holds its breath",
)


@dataclass(frozen=True)
class TurnResult:
    session_id: str
    turn_number: int
    player_text: str
    narration: str
    state: GameState
    events: list[Event]
    status: str
    reachable: list[ReachableDestination]
    incomplete_objectives: list[IncompleteObjective]
    enemies: list[EnemyStatus]


def _turn_guidance(state: GameState) -> tuple[
    list[ReachableDestination],
    list[IncompleteObjective],
    list[EnemyStatus],
]:
    return (
        reachable_destinations(state),
        incomplete_objectives(state),
        enemy_statuses(state),
    )


def _format_context(state: GameState, recent_turns: list[dict]) -> str:
    history_lines: list[str] = []
    for turn in recent_turns:
        history_lines.append(f"Player: {turn['player_text']}")
        history_lines.append(f"DM: {turn['narration']}")
    history = "\n".join(history_lines) if history_lines else "(no prior turns)"
    destinations = format_reachable_lines(reachable_destinations(state))
    objectives = format_incomplete_objective_lines(incomplete_objectives(state))
    enemies = format_enemy_status_lines(enemy_statuses(state))
    return (
        f"Current GameState JSON:\n{state.model_dump_json(indent=2)}\n\n"
        f"Reachable destinations:\n{destinations}\n\n"
        f"Incomplete objectives:\n{objectives}\n\n"
        f"Enemy groups:\n{enemies}\n\n"
        f"Recent turns:\n{history}\n\n"
        f"Rolling summary:\n{state.summary or '(empty)'}"
    )


def _format_turn_prompt(
    state: GameState,
    recent_turns: list[dict],
    player_text: str,
    *,
    intent: ValidatedActionIntent,
) -> str:
    return (
        f"{_format_context(state, recent_turns)}\n\n"
        f"Validated Action Intent:\n{format_validated_intent(intent)}\n\n"
        f"Player action:\n{player_text}\n\n"
        "Resolve the action using only the validated Action Intent ids. "
        "Call tools for any Check or roll before narrating the outcome. "
        "Use move_to only with a reachable destination id from the list above. "
        "Nudge the player toward incomplete objectives and reachable destinations "
        "when fictionally appropriate."
    )


def _tool_args(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    return {"value": raw}


def _rolling_label(tool_name: str, args: dict[str, Any]) -> str:
    reason = str(args.get("reason") or "").strip()
    if tool_name == "skill_check":
        skill = str(args.get("skill") or "unknown")
        dc = args.get("dc")
        base = f"Dice tumble for {skill}"
        if dc is not None:
            base = f"{base} (DC {dc})"
        return f"{base}..." if not reason else f"{base}: {reason}..."
    if tool_name == "saving_throw":
        ability = str(args.get("ability") or "unknown")
        dc = args.get("dc")
        base = f"Fate hangs on a {ability} save"
        if dc is not None:
            base = f"{base} (DC {dc})"
        return f"{base}..." if not reason else f"{base}: {reason}..."
    if tool_name == "roll_dice":
        expression = str(args.get("expression") or "dice")
        return f"Dice clatter — rolling {expression}..."
    if tool_name == "short_rest":
        return "Hit dice rattle as you settle into a short rest..."
    return "Dice tumble across the table..."


def _domain_stream_events(event: Event) -> list[TurnStreamEvent]:
    payload = event.model_dump(mode="json")
    emitted: list[TurnStreamEvent] = []
    if event.type in ROLL_EVENT_TYPES:
        emitted.append(RollEvent(event=payload))
    if event.type in STATE_EVENT_TYPES:
        emitted.append(StateChangedEvent(event=payload))
    return emitted


class TurnService:
    def __init__(
        self,
        store: EventStore,
        *,
        settings: Settings | None = None,
        model: Model | str | None = None,
        locks: SessionLockRegistry | None = None,
        intent: IntentProposer | None = None,
    ) -> None:
        self._store = store
        self._settings = settings or get_settings()
        self._model = model if model is not None else resolve_model(self._settings)
        self._agent = build_dm_agent(
            self._model,
            retries=self._settings.agent_retries,
        )
        self._locks = locks if locks is not None else SessionLockRegistry()
        self._intent: IntentProposer = intent if intent is not None else CodeIntentService()

    async def stream_turn(
        self, session_id: str, player_text: str
    ) -> AsyncIterator[TurnStreamEvent]:
        text = player_text.strip()
        if not text:
            raise ValueError("player_text must not be empty")

        lock = await self._locks.lock_for(session_id)
        async with lock:
            async for event in self._stream_turn_locked(session_id, text):
                yield event

    async def _resolve_intent(
        self,
        session_id: str,
        text: str,
        state: GameState,
    ) -> tuple[ValidatedActionIntent | None, TurnResult | None]:
        proposed = await self._intent.propose(text, state)
        validation = validate_action_intent(state, proposed)
        if validation.ok and validation.intent is not None:
            return validation.intent, None

        destinations = reachable_destinations(state)
        narration = rejected_intent_narration(validation.reason or "invalid Action Intent")
        turn_number = await self._store.add_turn(
            session_id,
            player_text=text,
            narration=narration,
            status="no_progress",
        )
        progress_events = await self._apply_progress(session_id)
        fresh = await self._store.get_snapshot(session_id)
        assert fresh is not None
        reachable, objectives, enemies = _turn_guidance(fresh)
        return None, TurnResult(
            session_id=session_id,
            turn_number=turn_number,
            player_text=text,
            narration=narration,
            state=fresh,
            events=list(progress_events),
            status="no_progress",
            reachable=reachable,
            incomplete_objectives=objectives,
            enemies=enemies,
        )

    async def _stream_turn_locked(
        self, session_id: str, text: str
    ) -> AsyncIterator[TurnStreamEvent]:
        state = await self._store.get_snapshot(session_id)
        if state is None:
            raise KeyError(f"session not found: {session_id}")

        validated, rejected = await self._resolve_intent(session_id, text, state)
        if rejected is not None:
            yield DoneEvent(
                turn_number=rejected.turn_number,
                status=rejected.status,
                state=rejected.state,
                narration=rejected.narration,
                reachable=list(rejected.reachable),
                incomplete_objectives=list(rejected.incomplete_objectives),
                enemies=list(rejected.enemies),
            )
            return
        assert validated is not None

        recent = await self._store.list_recent_turns(
            session_id,
            limit=self._settings.memory_recent_turns,
        )
        deps = TurnDeps(store=self._store, session_id=session_id)
        prompt = _format_turn_prompt(state, recent, text, intent=validated)

        status = "ok"
        narration_parts: list[str] = []
        emitted_domain = 0
        await_tick = 0

        yield ProgressEvent(
            phase="awaiting_dm",
            label=_AWAITING_OPENERS[0],
        )

        try:
            async with self._agent.run_stream_events(
                prompt,
                deps=deps,
                usage_limits=UsageLimits(
                    request_limit=self._settings.max_tool_calls_per_turn + 2,
                    tool_calls_limit=self._settings.max_tool_calls_per_turn,
                ),
            ) as run:
                async for agent_event in run:
                    if isinstance(agent_event, FunctionToolCallEvent):
                        args = _tool_args(agent_event.part.args)
                        tool_name = agent_event.part.tool_name
                        if tool_name in ROLLING_TOOLS:
                            yield ProgressEvent(
                                phase="rolling",
                                label=_rolling_label(tool_name, args),
                            )
                        else:
                            await_tick += 1
                            yield ProgressEvent(
                                phase="awaiting_dm",
                                label=_AWAITING_OPENERS[await_tick % len(_AWAITING_OPENERS)],
                            )
                        yield ToolCallEvent(tool_name=tool_name, args=args)
                    elif isinstance(agent_event, FunctionToolResultEvent):
                        new_events = deps.events_this_turn[emitted_domain:]
                        emitted_domain = len(deps.events_this_turn)
                        emitted_roll = False
                        for domain_event in new_events:
                            for stream_event in _domain_stream_events(domain_event):
                                if isinstance(stream_event, RollEvent):
                                    emitted_roll = True
                                yield stream_event
                        if emitted_roll and not narration_parts:
                            await_tick += 1
                            yield ProgressEvent(
                                phase="awaiting_dm",
                                label=_AWAITING_AFTER_ROLL[await_tick % len(_AWAITING_AFTER_ROLL)],
                            )
                    elif isinstance(agent_event, PartStartEvent) and isinstance(
                        agent_event.part, TextPart
                    ):
                        if agent_event.part.content:
                            narration_parts.append(agent_event.part.content)
                            yield NarrationDelta(text=agent_event.part.content)
                    elif isinstance(agent_event, PartDeltaEvent) and isinstance(
                        agent_event.delta, TextPartDelta
                    ):
                        if agent_event.delta.content_delta:
                            narration_parts.append(agent_event.delta.content_delta)
                            yield NarrationDelta(text=agent_event.delta.content_delta)
                    elif isinstance(agent_event, AgentRunResultEvent):
                        output = str(agent_event.result.output).strip()
                        if output and not narration_parts:
                            narration_parts.append(output)
                            yield NarrationDelta(text=output)
        except Exception as exc:  # noqa: BLE001 - persist aborted Turn
            status = "aborted"
            message = f"The Turn could not be completed: {exc}"
            narration_parts = [message]
            yield ErrorEvent(message=message)

        # Flush any domain Events not tied to a tool-result callback
        new_events = deps.events_this_turn[emitted_domain:]
        for domain_event in new_events:
            for stream_event in _domain_stream_events(domain_event):
                yield stream_event

        narration = "".join(narration_parts).strip() or "The world holds its breath."
        turn_number = await self._store.add_turn(
            session_id,
            player_text=text,
            narration=narration,
            status=status,
        )
        progress_events = await self._apply_progress(session_id)
        for domain_event in progress_events:
            deps.events_this_turn.append(domain_event)
            for stream_event in _domain_stream_events(domain_event):
                yield stream_event
        fresh_state = await self._store.get_snapshot(session_id)
        assert fresh_state is not None
        reachable, objectives, enemies = _turn_guidance(fresh_state)
        yield DoneEvent(
            turn_number=turn_number,
            status=status,
            state=fresh_state,
            narration=narration,
            reachable=reachable,
            incomplete_objectives=objectives,
            enemies=enemies,
        )

    async def run_turn(self, session_id: str, player_text: str) -> TurnResult:
        text = player_text.strip()
        if not text:
            raise ValueError("player_text must not be empty")

        lock = await self._locks.lock_for(session_id)
        async with lock:
            return await self._run_turn_locked(session_id, text)

    async def _run_turn_locked(self, session_id: str, text: str) -> TurnResult:
        state = await self._store.get_snapshot(session_id)
        if state is None:
            raise KeyError(f"session not found: {session_id}")

        validated, rejected = await self._resolve_intent(session_id, text, state)
        if rejected is not None:
            return rejected
        assert validated is not None

        recent = await self._store.list_recent_turns(
            session_id,
            limit=self._settings.memory_recent_turns,
        )
        deps = TurnDeps(store=self._store, session_id=session_id)
        prompt = _format_turn_prompt(state, recent, text, intent=validated)

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
        progress_events = await self._apply_progress(session_id)
        deps.events_this_turn.extend(progress_events)
        fresh_state = await self._store.get_snapshot(session_id)
        assert fresh_state is not None
        reachable, objectives, enemies = _turn_guidance(fresh_state)
        return TurnResult(
            session_id=session_id,
            turn_number=turn_number,
            player_text=text,
            narration=narration,
            state=fresh_state,
            events=list(deps.events_this_turn),
            status=status,
            reachable=reachable,
            incomplete_objectives=objectives,
            enemies=enemies,
        )

    async def _apply_progress(self, session_id: str) -> list[Event]:
        """Append Objective/Quest completion Events derived from current Snapshot."""
        state = await self._store.get_snapshot(session_id)
        if state is None:
            return []
        emitted: list[Event] = []
        for event in plan_progress_events(state):
            await self._store.append_event(session_id, event)
            emitted.append(event)
        return emitted
