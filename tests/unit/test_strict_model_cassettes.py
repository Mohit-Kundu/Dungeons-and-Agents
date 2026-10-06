"""Seam: StrictCassetteModel at the PydanticAI Model boundary (record/replay)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models import ModelRequestParameters
from pydantic_ai.models.function import AgentInfo, FunctionModel

from dnd_agent.agent.cassette import CassetteError, ModelRole, StrictCassetteModel
from dnd_agent.agent.deps import TurnDeps
from dnd_agent.agent.dm_agent import build_dm_agent
from dnd_agent.agent.recap import RecapService
from dnd_agent.store.event_store import EventStore
from dnd_agent.world.intent import IntentService, ProposedActionIntent


def _echo_model() -> FunctionModel:
    def reply(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        last = messages[-1]
        assert isinstance(last, ModelRequest)
        part = last.parts[0]
        assert isinstance(part, UserPromptPart)
        return ModelResponse(parts=[TextPart(content=f"echo:{part.content}")])

    return FunctionModel(reply)


def _messages(text: str) -> list[ModelMessage]:
    return [ModelRequest(parts=[UserPromptPart(content=text)])]


async def _record_echo(path: Path, *, role: ModelRole = "dm", text: str = "hello") -> None:
    params = ModelRequestParameters()
    recorder = StrictCassetteModel(
        _echo_model(),
        path=path,
        role=role,
        mode="record",
    )
    await recorder.request(_messages(text), None, params)


async def test_record_then_replay_request_round_trip(tmp_path: Path) -> None:
    cassette_path = tmp_path / "dm.json"
    params = ModelRequestParameters()

    recorder = StrictCassetteModel(
        _echo_model(),
        path=cassette_path,
        role="dm",
        mode="record",
    )
    recorded = await recorder.request(_messages("hello"), None, params)
    assert recorded.parts[0].content == "echo:hello"  # type: ignore[union-attr]
    assert cassette_path.is_file()

    replay = StrictCassetteModel(
        _echo_model(),
        path=cassette_path,
        role="dm",
        mode="replay",
    )
    replayed = await replay.request(_messages("hello"), None, params)
    assert replayed.parts[0].content == "echo:hello"  # type: ignore[union-attr]


async def test_replay_mismatch_raises_actionable_cassette_error(tmp_path: Path) -> None:
    cassette_path = tmp_path / "dm.json"
    await _record_echo(cassette_path, text="hello")

    replay = StrictCassetteModel(
        _echo_model(),
        path=cassette_path,
        role="dm",
        mode="replay",
    )
    with pytest.raises(CassetteError, match=r"mismatch|expected|got") as exc_info:
        await replay.request(_messages("different"), None, ModelRequestParameters())
    message = str(exc_info.value)
    assert "hello" in message
    assert "different" in message


async def test_replay_never_calls_wrapped_live_model(tmp_path: Path) -> None:
    cassette_path = tmp_path / "dm.json"
    await _record_echo(cassette_path)

    def boom(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise AssertionError("live provider must not be called during replay")

    replay = StrictCassetteModel(
        FunctionModel(boom),
        path=cassette_path,
        role="dm",
        mode="replay",
    )
    result = await replay.request(_messages("hello"), None, ModelRequestParameters())
    assert result.parts[0].content == "echo:hello"  # type: ignore[union-attr]


def _streaming_echo_model() -> FunctionModel:
    def reply(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        last = messages[-1]
        assert isinstance(last, ModelRequest)
        part = last.parts[0]
        assert isinstance(part, UserPromptPart)
        return ModelResponse(parts=[TextPart(content=f"echo:{part.content}")])

    async def stream(messages: list[ModelMessage], _info: AgentInfo):
        last = messages[-1]
        assert isinstance(last, ModelRequest)
        part = last.parts[0]
        assert isinstance(part, UserPromptPart)
        text = f"echo:{part.content}"
        for index in range(0, len(text), 4):
            yield text[index : index + 4]

    return FunctionModel(reply, stream_function=stream)


async def test_record_then_replay_streaming_round_trip(tmp_path: Path) -> None:
    cassette_path = tmp_path / "dm.json"
    params = ModelRequestParameters()

    recorder = StrictCassetteModel(
        _streaming_echo_model(),
        path=cassette_path,
        role="dm",
        mode="record",
    )
    async with recorder.request_stream(_messages("stream"), None, params) as stream:
        events = [event async for event in stream]
        recorded = stream.get()
    assert recorded.parts[0].content == "echo:stream"  # type: ignore[union-attr]
    assert events

    replay = StrictCassetteModel(
        _streaming_echo_model(),
        path=cassette_path,
        role="dm",
        mode="replay",
    )
    async with replay.request_stream(_messages("stream"), None, params) as stream:
        replay_events = [event async for event in stream]
        replayed = stream.get()
    assert replayed.parts[0].content == "echo:stream"  # type: ignore[union-attr]
    assert replay_events


async def test_roles_use_separate_cassette_files(tmp_path: Path) -> None:
    params = ModelRequestParameters()
    roles: list[tuple[ModelRole, str]] = [
        ("intent", "propose"),
        ("dm", "narrate"),
        ("recap", "summarize"),
    ]
    for role, text in roles:
        path = tmp_path / f"{role}.json"
        model = StrictCassetteModel(_echo_model(), path=path, role=role, mode="record")
        result = await model.request(_messages(text), None, params)
        assert result.parts[0].content == f"echo:{text}"  # type: ignore[union-attr]

    for role, text in roles:
        path = tmp_path / f"{role}.json"
        model = StrictCassetteModel(_echo_model(), path=path, role=role, mode="replay")
        result = await model.request(_messages(text), None, params)
        assert result.parts[0].content == f"echo:{text}"  # type: ignore[union-attr]

    dm_replay = StrictCassetteModel(
        _echo_model(),
        path=tmp_path / "dm.json",
        role="dm",
        mode="replay",
    )
    with pytest.raises(CassetteError, match="mismatch"):
        await dm_replay.request(_messages("propose"), None, params)


async def test_replay_exhausted_cassette_raises(tmp_path: Path) -> None:
    cassette_path = tmp_path / "dm.json"
    await _record_echo(cassette_path)
    replay = StrictCassetteModel(
        _echo_model(),
        path=cassette_path,
        role="dm",
        mode="replay",
    )
    await replay.request(_messages("hello"), None, ModelRequestParameters())
    with pytest.raises(CassetteError, match="exhausted"):
        await replay.request(_messages("hello"), None, ModelRequestParameters())


@pytest.fixture
async def store(tmp_path: Path) -> EventStore:
    event_store = EventStore(tmp_path / "cassette_roles.db")
    await event_store.open()
    return event_store


async def test_intent_dm_and_recap_round_trip_through_cassettes(
    tmp_path: Path,
    store: EventStore,
) -> None:
    state = await store.create_session(scenario_id="goblin_cave", rng_seed=1)

    def intent_reply(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                TextPart(
                    content=ProposedActionIntent(
                        kind="general",
                        confidence="high",
                        note="look around",
                    ).model_dump_json()
                )
            ]
        )

    def dm_reply(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content="The cave mouth is quiet.")])

    def recap_reply(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content="Brynn studied the cave mouth.")])

    def boom(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise AssertionError("live provider must not be called during replay")

    intent_path = tmp_path / "intent.json"
    dm_path = tmp_path / "dm.json"
    recap_path = tmp_path / "recap.json"

    recorded_intent = await IntentService(
        StrictCassetteModel(
            FunctionModel(intent_reply),
            path=intent_path,
            role="intent",
            mode="record",
        )
    ).propose("I look around.", state)

    dm_agent = build_dm_agent(
        StrictCassetteModel(
            FunctionModel(dm_reply),
            path=dm_path,
            role="dm",
            mode="record",
        )
    )
    dm_deps = TurnDeps(store=store, session_id=state.session_id)
    dm_result = await dm_agent.run("Narrate the cave mouth.", deps=dm_deps)
    recorded_dm = str(dm_result.output)

    recorded_recap = await RecapService(
        StrictCassetteModel(
            FunctionModel(recap_reply),
            path=recap_path,
            role="recap",
            mode="record",
        )
    ).generate(
        prior_summary="",
        turns=[
            {
                "turn_number": 1,
                "player_text": "I look around.",
                "narration": recorded_dm,
            }
        ],
    )

    assert recorded_intent.kind == "general"
    assert recorded_dm == "The cave mouth is quiet."
    assert recorded_recap == "Brynn studied the cave mouth."

    replayed_intent = await IntentService(
        StrictCassetteModel(FunctionModel(boom), path=intent_path, role="intent", mode="replay")
    ).propose("I look around.", state)
    assert replayed_intent == recorded_intent

    dm_replay_agent = build_dm_agent(
        StrictCassetteModel(FunctionModel(boom), path=dm_path, role="dm", mode="replay")
    )
    replayed_dm = str(
        (await dm_replay_agent.run("Narrate the cave mouth.", deps=dm_deps)).output
    )
    assert replayed_dm == recorded_dm

    replayed_recap = await RecapService(
        StrictCassetteModel(FunctionModel(boom), path=recap_path, role="recap", mode="replay")
    ).generate(
        prior_summary="",
        turns=[
            {
                "turn_number": 1,
                "player_text": "I look around.",
                "narration": recorded_dm,
            }
        ],
    )
    assert replayed_recap == recorded_recap
