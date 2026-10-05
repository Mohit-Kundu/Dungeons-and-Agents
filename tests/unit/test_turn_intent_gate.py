"""Seam: TurnService rejects unavailable Action Intents before the DM runs."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.domain.events import LocationChanged
from dnd_agent.services.turns import TurnService
from dnd_agent.store.event_store import EventStore
from dnd_agent.world.intent import IntentService, ProposedActionIntent


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "intent_turns.db")
    await event_store.open()
    return event_store


class StubIntentService:
    def __init__(self, proposed: ProposedActionIntent) -> None:
        self.proposed = proposed
        self.calls = 0

    async def propose(self, player_text: str, state) -> ProposedActionIntent:
        self.calls += 1
        return self.proposed


def _dm_that_must_not_run() -> FunctionModel:
    async def boom(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise AssertionError("DM agent must not run for rejected Action Intent")

    return FunctionModel(boom)


def _dm_that_records_prompt(seen: dict[str, str]) -> FunctionModel:
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        blobs: list[str] = []
        for message in messages:
            for part in message.parts:
                content = getattr(part, "content", None)
                if isinstance(content, str):
                    blobs.append(content)
        joined = "\n".join(blobs)
        if "Validated Action Intent" in joined:
            seen["prompt"] = joined
        return ModelResponse(parts=[TextPart(content="You study the muddy tracks.")])

    return FunctionModel(reply)


async def test_rejected_remote_item_is_no_progress_without_dm(store: EventStore) -> None:
    intent = StubIntentService(
        ProposedActionIntent(
            kind="use",
            item_ids=["stolen_goods"],
            confidence="high",
        )
    )
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)
    service = TurnService(store, model=_dm_that_must_not_run(), intent=intent)

    result = await service.run_turn(state.session_id, "I grab the stolen goods.")

    assert intent.calls == 1
    assert result.status == "no_progress"
    assert result.events == []
    assert "unavailable" in result.narration.lower() or "not" in result.narration.lower()
    turns = await store.list_recent_turns(state.session_id, limit=1)
    assert turns[0]["status"] == "no_progress"


async def test_rejected_ambiguous_intent_is_no_progress(store: EventStore) -> None:
    intent = StubIntentService(
        ProposedActionIntent(
            kind="interact",
            interactable_ids=["muddy_tracks", "war_drum"],
            confidence="high",
            ambiguous=True,
        )
    )
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=2)
    service = TurnService(store, model=_dm_that_must_not_run(), intent=intent)

    result = await service.run_turn(state.session_id, "I poke the thing.")

    assert result.status == "no_progress"
    assert "ambiguous" in result.narration.lower()


async def test_rejected_uncertain_intent_is_no_progress(store: EventStore) -> None:
    intent = StubIntentService(ProposedActionIntent(kind="general", confidence="low"))
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=3)
    service = TurnService(store, model=_dm_that_must_not_run(), intent=intent)

    result = await service.run_turn(state.session_id, "Maybe I do something?")

    assert result.status == "no_progress"
    assert "uncertain" in result.narration.lower() or "confidence" in result.narration.lower()


async def test_valid_intent_reaches_dm_with_allowed_ids(store: EventStore) -> None:
    seen: dict[str, str] = {}
    intent = StubIntentService(
        ProposedActionIntent(
            kind="interact",
            interactable_ids=["muddy_tracks"],
            confidence="high",
        )
    )
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=4)
    service = TurnService(store, model=_dm_that_records_prompt(seen), intent=intent)

    result = await service.run_turn(state.session_id, "I examine the muddy tracks.")

    assert result.status == "ok"
    assert "Validated Action Intent" in seen["prompt"]
    assert "muddy_tracks" in seen["prompt"]
    assert "interact" in seen["prompt"]


async def test_illegal_travel_intent_replaces_d023_heuristic(store: EventStore) -> None:
    intent = StubIntentService(
        ProposedActionIntent(
            kind="travel",
            destination_id="goblin_den",
            confidence="high",
        )
    )
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=5)
    service = TurnService(store, model=_dm_that_must_not_run(), intent=intent)

    result = await service.run_turn(state.session_id, "I go to the Goblin Den.")

    assert result.status == "no_progress"
    assert "no route" in result.narration.lower()
    assert not any(
        isinstance(event, LocationChanged) for event in await store.list_events(state.session_id)
    )


async def test_intent_service_function_model_proposes_structured_intent(
    store: EventStore,
) -> None:
    async def reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                TextPart(
                    content=ProposedActionIntent(
                        kind="travel",
                        destination_id="twisting_tunnel",
                        confidence="high",
                    ).model_dump_json()
                )
            ]
        )

    state = await store.create_session(scenario_id="goblin_cave", rng_seed=6)
    service = IntentService(FunctionModel(reply))
    proposed = await service.propose("I enter the twisting tunnel.", state)

    assert proposed.kind == "travel"
    assert proposed.destination_id == "twisting_tunnel"
    assert proposed.confidence == "high"
