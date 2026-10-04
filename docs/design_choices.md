# Design Choices

Growing, append-only log of design decisions. Entries are numbered `D-NNN`. Never edit an accepted entry in place: mark it `superseded by D-0xx` and add a new entry.

## Entry template

```markdown
### D-NNN: Title

- **Date:** YYYY-MM-DD
- **Status:** accepted | superseded by D-0xx
- **Context:** Why a decision was needed
- **Options considered:**
  - Option A — pros / cons
  - Option B — pros / cons
- **Decision:** What we chose
- **Consequences:** What this commits us to
```

---

### D-001: Python 3.12 as the implementation language

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Choose a runtime for the POC that fits LLM tooling, validation, and later RAG/evals.
- **Options considered:**
  - Python 3.12 + Pydantic — best LLM/RAG/eval ecosystem; weaker end-to-end types than TypeScript
  - TypeScript/Node + Zod — strong types and easier future web UI; thinner data/eval tooling for later phases
- **Decision:** Python 3.12 with Pydantic.
- **Consequences:** Package layout under `src/dnd_agent/`; tests with pytest; a future web UI may be a second language or a Python UI framework.

### D-002: PydanticAI as the only agent framework for the POC

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Need typed tools, structured outputs, and a multi-provider model layer without heavy orchestration yet.
- **Options considered:**
  - PydanticAI only — least ceremony for a single DM agent; no built-in checkpointing/undo
  - LangGraph + PydanticAI — checkpointing and graph routing from day one; steeper ramp and overlapping state models
  - Hand-rolled tool loop — maximum control; rebuilds provider adapters and retries
- **Decision:** PydanticAI only for the POC. Add a graph layer later if combat or multi-agent split needs it.
- **Consequences:** Turn loop lives in application services + the agent’s tool loop, not a graph runtime.

### D-003: Gemini as the default model provider

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Need a default cloud model with a path to OpenAI (including Luna) and local Ollama.
- **Options considered:**
  - Thin custom adapter — full control; extra code to maintain
  - PydanticAI’s native multi-provider models — covers Gemini, OpenAI, and Ollama; less custom glue
  - Claude-only or OpenAI-only — simpler; harder to swap
  - Ollama-only — free/private; weak tool calling on small models
- **Decision:** Use PydanticAI model strings; default `google-gla:gemini-2.5-flash`; support OpenAI and Ollama via config.
- **Consequences:** Settings expose `DND_MODEL` and provider keys; live smoke tests are opt-in and per-provider.

### D-004: FastAPI backend with Typer/Rich CLI client

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Choose a player interface that is fast to build but leaves an API seam for later clients.
- **Options considered:**
  - Terminal CLI only — fastest; no HTTP seam
  - FastAPI + CLI client — API from day one; more scaffolding
  - Streamlit/Gradio web UI — shareable UI; fighty with a stateful game loop
- **Decision:** FastAPI backend + Typer/Rich CLI over HTTP.
- **Consequences:** CLI talks only to the API; future web/multiplayer clients can reuse the same endpoints.

### D-005: Stream turns with Server-Sent Events

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Narration should feel live; tool/roll events should be visible as they happen.
- **Options considered:**
  - SSE — simple one-way stream; good fit for narration + event feed
  - Plain JSON request/response — simpler; no progressive feedback
  - WebSockets — bidirectional; more complexity than the POC needs
- **Decision:** `POST /sessions/{id}/turns` streams SSE events (`narration_delta`, `tool_call`, `roll`, `state_changed`, `error`, `done`).
- **Consequences:** CLI must consume SSE; API tests cover the event contract.

### D-006: SQLite append-only event log with snapshots

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** State must be accurate, auditable, and replayable; the LLM must not own it.
- **Options considered:**
  - SQLite events + snapshots — durable, queryable, single-file; enough for one player
  - JSON file per session — trivial; weak concurrency and querying
  - Postgres — production-ready; heavier for a local POC
- **Decision:** SQLite event store; snapshots cached; reducer rebuilds state from events.
- **Consequences:** Replay-equals-snapshot is a hard invariant; failed turns cannot discard committed rolls.

### D-007: Typed tools instead of generic state patches

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** The early architecture sketch proposed `update_state(patch)`; free-form patches are hard to validate and easy for the model to misuse.
- **Options considered:**
  - Generic `update_state(patch)` — flexible; weak validation and prompt discipline
  - Typed tools (`skill_check`, `apply_damage`, `add_item`, …) — clearer for the model; more tools to document
- **Decision:** Specific typed tools that validate preconditions and emit Events.
- **Consequences:** Tool surface is the agent API; refused tools return errors without mutating state.

### D-008: SRD 5.2 non-combat rules slice for the POC

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Scope must stay small enough to ship a playable slice quickly.
- **Options considered:**
  - Minimal checks/HP/inventory only — smallest; thin mechanical feel
  - Minimal plus saves, conditions, rests — still no combat; richer play
  - Include basic combat — high value; large design surface
- **Decision:** Ability/skill checks, advantage/disadvantage, saving throws, conditions, short/long rests, HP, inventory. No combat engine yet.
- **Consequences:** Scenario design stays exploration/social/skill-focused; combat is roadmap.

### D-009: Commit events as they happen (no re-roll on abort)

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Honesty of dice is a product requirement; aborting a turn must not let the model retry a bad roll.
- **Options considered:**
  - Commit events immediately — honest dice; aborted turns leave partial history
  - Buffer until turn success — cleaner history; enables silent re-rolls
- **Decision:** Persist Events as tools succeed; mark turns `ok` or `aborted`.
- **Consequences:** Event log may include events from aborted turns; snapshots always reflect committed events.

### D-010: Tooling and project logs

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Need a repeatable local workflow and a durable record of decisions/changes.
- **Options considered:**
  - uv + Ruff + Pyright + Pytest/Hypothesis — modern Python defaults
  - Poetry/Pipenv + mypy — familiar; slower/heavier for this stack
  - ADRs only vs growing design log — ADRs are one-file-per-decision; a growing log is simpler for this repo
- **Decision:** uv, Ruff, Pyright, Pytest, Hypothesis, pytest-asyncio; maintain `CHANGELOG.md`, `GLOSSARY.md`, `docs/devlog.md`, and `docs/design_choices.md`; require log updates in `AGENTS.md`.
- **Consequences:** Skills read `docs/design_choices.md` for decisions instead of `docs/adr/` for this project.

### D-011: Content files for starter Character and Scenario

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 02 needs a predefined Session bootstrap without character creation.
- **Options considered:**
  - Hardcode in Python — fast; mixes data with code
  - JSON/YAML under `content/` — editable, clear seam for later content packs
- **Decision:** `content/characters/*.json` and `content/scenarios/*.yaml` loaded by `dnd_agent.content.loader`.
- **Consequences:** Scenario points at a `character_id`; changing starter kits does not require code edits.
