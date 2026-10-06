"""Strict model cassettes: record/replay at the PydanticAI Model boundary."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelResponse,
    ModelResponseStreamEvent,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import RunContext

CassetteMode = Literal["record", "replay", "live"]
ModelRole = Literal["intent", "dm", "recap"]


class CassetteError(RuntimeError):
    """Actionable cassette failure (mismatch, exhausted, or live call in replay)."""


def _strip_volatile(value: Any) -> Any:
    """Drop timestamps and other non-deterministic fields from dumped structures."""
    if isinstance(value, dict):
        return {
            key: _strip_volatile(item)
            for key, item in value.items()
            if key not in {"timestamp", "id", "run_id", "conversation_id"}
        }
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    return value


def request_fingerprint(
    messages: list[ModelMessage],
    model_settings: ModelSettings | None,
    model_request_parameters: ModelRequestParameters,
) -> dict[str, Any]:
    dumped = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    return {
        "messages": _strip_volatile(dumped),
        "model_settings": _strip_volatile(model_settings) if model_settings else None,
        "allow_text_output": model_request_parameters.allow_text_output,
        "allow_image_output": model_request_parameters.allow_image_output,
        "output_mode": model_request_parameters.output_mode,
        "function_tools": sorted(t.name for t in model_request_parameters.function_tools),
        "output_tools": sorted(t.name for t in model_request_parameters.output_tools),
    }


def _fingerprint_summary(fingerprint: dict[str, Any]) -> str:
    messages = fingerprint.get("messages") or []
    texts: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        for part in message.get("parts") or []:
            if isinstance(part, dict) and isinstance(part.get("content"), str):
                texts.append(part["content"][:80])
    preview = " | ".join(texts) if texts else "(no text parts)"
    tools = fingerprint.get("function_tools") or []
    return f"tools={tools!r} text={preview!r}"


@dataclass
class CassetteInteraction:
    fingerprint: dict[str, Any]
    response: ModelResponse

    def to_json(self) -> dict[str, Any]:
        response_dump = ModelMessagesTypeAdapter.dump_python([self.response], mode="json")[0]
        return {
            "fingerprint": self.fingerprint,
            "response": response_dump,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CassetteInteraction:
        response = ModelMessagesTypeAdapter.validate_python([data["response"]])[0]
        assert isinstance(response, ModelResponse)
        return cls(fingerprint=data["fingerprint"], response=response)


class CassetteStore:
    """JSON cassette file for one ModelRole."""

    def __init__(self, path: Path, role: ModelRole) -> None:
        self.path = path
        self.role = role
        self._interactions: list[CassetteInteraction] = []
        self._cursor = 0
        self.model_name = "cassette"
        self.system = "cassette"

    def load(self) -> None:
        if not self.path.is_file():
            raise CassetteError(f"cassette file missing for role={self.role!r}: {self.path}")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("role") != self.role:
            raise CassetteError(
                f"cassette role mismatch: file has {raw.get('role')!r}, expected {self.role!r}"
            )
        self.model_name = str(raw.get("model_name") or "cassette")
        self.system = str(raw.get("system") or "cassette")
        self._interactions = [CassetteInteraction.from_json(item) for item in raw["interactions"]]
        self._cursor = 0

    def load_existing_for_append(self) -> None:
        """If a cassette file already exists, load its interactions for continued recording."""
        if not self.path.is_file():
            return
        self.load()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "role": self.role,
            "model_name": self.model_name,
            "system": self.system,
            "interactions": [item.to_json() for item in self._interactions],
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def append(self, interaction: CassetteInteraction) -> None:
        self._interactions.append(interaction)
        self.save()

    def next_matching(self, fingerprint: dict[str, Any]) -> CassetteInteraction:
        if self._cursor >= len(self._interactions):
            raise CassetteError(
                f"cassette exhausted for role={self.role!r} at index {self._cursor}; "
                f"incoming request: {_fingerprint_summary(fingerprint)}"
            )
        expected = self._interactions[self._cursor]
        if expected.fingerprint != fingerprint:
            raise CassetteError(
                f"cassette request mismatch for role={self.role!r} at index {self._cursor}: "
                f"expected {_fingerprint_summary(expected.fingerprint)}; "
                f"got {_fingerprint_summary(fingerprint)}"
            )
        self._cursor += 1
        return expected


class _ReplayGuardModel(Model):
    """Inner model used in replay mode; any live call is a hard error."""

    def __init__(self, *, model_name: str, system: str) -> None:
        super().__init__()
        self._model_name = model_name
        self._system = system

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return self._system

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        raise CassetteError("replay mode refused to call a live provider")

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ):
        raise CassetteError("replay mode refused to call a live provider")
        # Unreachable; keeps this an async generator for the contextmanager decorator.
        yield  # type: ignore[misc]


@dataclass
class _ReplayStreamedResponse(StreamedResponse):
    _model_name: str
    _system: str
    _final: ModelResponse
    _timestamp: datetime

    def __init__(
        self,
        model_request_parameters: ModelRequestParameters,
        *,
        model_name: str,
        system: str,
        response: ModelResponse,
    ) -> None:
        super().__init__(model_request_parameters)
        self._model_name = model_name
        self._system = system
        self._final = response
        self._timestamp = response.timestamp or datetime.now(UTC)

    async def _get_event_iterator(self) -> AsyncIterator[ModelResponseStreamEvent]:
        for index, part in enumerate(self._final.parts):
            if isinstance(part, TextPart):
                for event in self._parts_manager.handle_text_delta(
                    vendor_part_id=str(index),
                    content=part.content,
                ):
                    yield event
            elif isinstance(part, ToolCallPart):
                maybe = self._parts_manager.handle_tool_call_delta(
                    vendor_part_id=str(index),
                    tool_name=part.tool_name,
                    args=part.args_as_json_str(),
                    tool_call_id=part.tool_call_id,
                )
                if maybe is not None:
                    yield maybe

    def get(self) -> ModelResponse:
        return self._final

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def provider_name(self) -> str | None:
        return self._system

    @property
    def provider_url(self) -> str | None:
        return None

    @property
    def timestamp(self) -> datetime:
        return self._timestamp


class StrictCassetteModel(WrapperModel):
    """Record or replay Model.request / Model.request_stream; never soft-fallback in replay."""

    _mode: CassetteMode
    _role: ModelRole
    _store: CassetteStore

    def __init__(
        self,
        wrapped: Model,
        *,
        path: Path,
        role: ModelRole,
        mode: CassetteMode,
    ) -> None:
        if mode == "live":
            super().__init__(wrapped)
            self._mode = mode
            self._role = role
            self._store = CassetteStore(path, role)
            return

        if mode == "replay":
            store = CassetteStore(path, role)
            store.load()
            super().__init__(_ReplayGuardModel(model_name=store.model_name, system=store.system))
            self._mode = mode
            self._role = role
            self._store = store
            return

        # record
        super().__init__(wrapped)
        self._mode = mode
        self._role = role
        self._store = CassetteStore(path, role)
        self._store.model_name = wrapped.model_name
        self._store.system = wrapped.system
        self._store.load_existing_for_append()

    @property
    def mode(self) -> CassetteMode:
        return self._mode

    @property
    def role(self) -> ModelRole:
        return self._role

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        if self._mode == "live":
            return await self.wrapped.request(messages, model_settings, model_request_parameters)

        fingerprint = request_fingerprint(messages, model_settings, model_request_parameters)
        if self._mode == "replay":
            return self._store.next_matching(fingerprint).response

        response = await self.wrapped.request(messages, model_settings, model_request_parameters)
        self._store.append(CassetteInteraction(fingerprint=fingerprint, response=response))
        return response

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ):
        if self._mode == "live":
            async with self.wrapped.request_stream(
                messages, model_settings, model_request_parameters, run_context
            ) as stream:
                yield stream
            return

        fingerprint = request_fingerprint(messages, model_settings, model_request_parameters)
        if self._mode == "replay":
            interaction = self._store.next_matching(fingerprint)
            yield _ReplayStreamedResponse(
                model_request_parameters,
                model_name=self.model_name,
                system=self.system,
                response=interaction.response,
            )
            return

        async with self.wrapped.request_stream(
            messages, model_settings, model_request_parameters, run_context
        ) as stream:
            try:
                yield stream
            finally:
                response = stream.get()
                self._store.append(CassetteInteraction(fingerprint=fingerprint, response=response))


def wrap_model(
    model: Model,
    *,
    path: Path,
    role: ModelRole,
    mode: CassetteMode,
) -> Model:
    """Return model unchanged for live; otherwise a StrictCassetteModel."""
    if mode == "live":
        return model
    return StrictCassetteModel(model, path=path, role=role, mode=mode)
