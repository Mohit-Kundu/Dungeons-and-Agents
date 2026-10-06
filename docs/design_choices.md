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
- **Status:** superseded by D-016
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

### D-012: Advance RNG seed on each dice Event

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Seeded dice must be deterministic across process restarts without replaying every prior `randint` call shape.
- **Options considered:**
  - Store call count and replay N draws — fragile if draw sizes differ
  - Persist `next_rng_seed` on each roll/Check Event — simple, replay-safe
- **Decision:** Each `DiceRolled` / `SkillCheckResolved` carries `next_rng_seed`; Reducer writes it to GameState.
- **Consequences:** Replay uses recorded totals; live play always constructs `DiceRng(state.rng_seed)`.

### D-013: JSON Turn responses until SSE ticket

- **Date:** 2026-10-04
- **Status:** superseded by D-015
- **Context:** D-005 chose SSE for turns, but ticket 03 only requires a playable Turn; ticket 05 owns streaming.
- **Options considered:**
  - Implement SSE in ticket 03 — meets D-005 early; larger blast radius
  - Ship JSON `PlayTurnResponse` now, SSE in ticket 05 — matches ticket split
- **Decision:** Ticket 03 uses JSON turns; ticket 05 upgrades the same route to SSE event types from D-005.
- **Consequences:** CLI `play` reads a full JSON body today; streaming clients wait for ticket 05. D-005 remains the target contract.

### D-014: POC Condition set and rest bookkeeping

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 04 needs Conditions, Saves, and rests without a full combat ruleset.
- **Options considered:**
  - Full SRD condition list + combat-only effects — complete; mostly inert for exploration
  - Small POC set with check/save-relevant effects + `hit_die` on Character — playable slice
  - Data-driven YAML condition packs — flexible; premature for five names
- **Decision:** Support `poisoned`, `frightened`, `restrained`, `blinded`, `prone` in code; Character stores `hit_die`; short rest spends hit dice (die + CON); long rest restores HP, half hit dice (rounded up), and clears tracked Conditions.
- **Consequences:** Tools reject unknown Conditions; combat-only prone/blinded attack effects wait for a combat engine; expanding the catalog is a content/rules change, not a sheet schema change.

### D-015: Upgrade Turns to SSE streaming

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 05 delivers D-005; D-013’s temporary JSON Turn body must go away.
- **Options considered:**
  - Keep JSON + optional `?stream=1` — compatible; two clients to maintain
  - Replace `POST /turns` with SSE only — one contract; breaks interim JSON clients
- **Decision:** `POST /sessions/{id}/turns` returns `text/event-stream` with `narration_delta`, `tool_call`, `roll`, `state_changed`, `error`, `done`. A shared `SessionLockRegistry` on app state serializes concurrent Turns per Session.
- **Consequences:** CLI consumes SSE; FunctionModel tests need `stream_function` for stream paths; `run_turn` remains for non-stream unit/agent tests.

### D-016: Resolve Models from DND_* Settings

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 06 needs Gemini / OpenAI / Ollama without rules/store changes; ambient provider env vars alone ignore our `DND_*` keys. Supersedes D-003’s “pass raw model strings” approach while keeping Gemini as the default.
- **Options considered:**
  - Pass raw `settings.model` strings to PydanticAI — simple; misses `DND_GEMINI_API_KEY` / Ollama URL wiring
  - `resolve_model(settings)` constructing provider-specific Models — explicit; small adapter
- **Decision:** Default `DND_MODEL=google-gla:gemini-2.5-flash`. Parse `provider:model`; build `GoogleModel` / `OpenAIChatModel` / `OllamaModel` with `DND_*` keys and optional `DND_OPENAI_BASE_URL` (Luna/proxies) or `DND_OLLAMA_BASE_URL`. Fail with `ProviderConfigError` when required creds are missing. Live smokes stay opt-in.
- **Consequences:** TurnService defaults to `resolve_model`; pytest excludes `@pytest.mark.live` by default.

### D-017: Scenario briefing seeds Session summary

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 07 needs a playable Scenario loop; `intro` was loaded but never shown to player or DM.
- **Options considered:**
  - Print intro only in the CLI — player sees it; agent context still empty
  - Put intro/locations/beats into `SessionCreated.summary` — one briefing for CLI + Turn prompts
  - New GameState fields for locations — clearer model; larger schema change for POC
- **Decision:** Extend scenario YAML with `locations`, `beats`, and `notes`; `Scenario.briefing()` becomes `SessionCreated.summary`; CLI `new` prints it.
- **Consequences:** Rolling summary compression (ticketed later) must preserve or replace this seed deliberately.

### D-018: Live Turn progress phases for anticipation

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** LLM latency between player input and narration feels empty; players need to see dice and waiting without raw tool dumps.
- **Options considered:**
  - CLI-only spinner guessing from existing `tool_call` / `roll` events — no server contract; weak copy
  - New `progress` SSE events with `awaiting_dm` / `rolling` phases plus player-facing labels — shared contract; CLI animates waits
  - Always print raw tool args — transparent; breaks immersion
- **Decision:** Emit `progress` at Turn start, before rolling Tools, and after roll reveals while awaiting narration. CLI hides raw `tool_call` lines, animates waits with cycling ellipsis, and prints permanent dramatic Check/Save/roll outcomes.
- **Consequences:** SSE contract includes `progress`; clients should clear status UI before `narration_delta` / `error` / `done`.

### D-019: Persist LLM Recap after every Turn

- **Date:** 2026-10-04
- **Status:** superseded by D-022
- **Context:** Returning players need to know what happened so far and what happened last; Briefing alone is not enough after play starts.
- **Options considered:**
  - Generate Recap only on Session load — always fresh; slows restore and costs a call each load
  - Persist Recap after every Turn via `SummaryUpdated` into `GameState.summary` — instant restore; extra model call per Turn
  - Refresh every N Turns only — cheaper; can omit intermediate detail
- **Decision:** After each successful Turn, a no-tools Recap agent folds prior `summary` + latest exchange + mechanical Events into a new Recap; append `SummaryUpdated`. Failures keep the prior Recap and do not abort the Turn. Emit `progress` phase `updating_recap` during the wait. `GET /sessions/{id}/overview` returns Snapshot + latest Turn; CLI `state` and pre-`play` show both.
- **Consequences:** `GameState.summary` evolves from Briefing seed into the rolling Recap; latest action stays in the turns table, not on GameState. Aborted Turns do not rewrite the Recap.

### D-020: Authoritative playable facts with fail-closed intent validation

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Prompt rules cannot guarantee that the DM Agent will not use an item, target, enemy, or destination absent from the Character's inventory or current surroundings.
- **Options considered:**
  - Prompt and Tool errors only — smallest change; illegal actions can still appear in narration
  - Require structured player commands — deterministic; weakens natural-language play
  - Extract structured intent, validate it against Scenario-backed GameState, then invoke the DM — natural input with enforceable state boundaries
- **Decision:** Scenario content and event-sourced GameState own all playable items, interactables, enemies, objectives, and exits. A fail-closed intent step resolves stable IDs and rejects unavailable or ambiguous targets before DM narration. The DM may invent sensory flavor, but flavor is not mechanically usable.
- **Consequences:** Scenario authoring and Turn latency increase; invalid attempts are recorded as no-progress Turns; legacy Sessions need deterministic lazy upgrade.

### D-021: Check-based encounters use deterministic enemy-group health

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** The POC needs enemy health, damage deductions, remaining counts, and all-defeated detection without introducing full initiative and action economy.
- **Options considered:**
  - Full combat engine — highest fidelity; too large for this milestone
  - Individual enemy state — precise targeting; more state and content
  - Homogeneous enemy groups with aggregate HP and check-based predefined damage — deterministic and incremental
- **Decision:** Scenario enemy groups declare count, HP per enemy, and deterministic resolution damage. Successful qualifying Checks permit typed Tools to deduct aggregate HP; code derives remaining count, prevents underflow, and owns defeat and Quest predicates.
- **Consequences:** Enemies within a group are mechanically interchangeable; narration cannot alter HP or defeat state; full combat remains future work.

### D-022: Refresh Recaps lazily on restore or command

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** D-019 adds model latency and cost to every successful Turn even though Recaps are primarily needed when returning to a Session or explicitly reviewing it.
- **Options considered:**
  - Keep per-Turn Recaps — instant restore; recurring cost and Turn latency
  - Render structured state without an LLM — reliable and fast; loses narrative continuity
  - Incrementally refresh after the last watermark on restore or explicit command — fresh when needed; restore/command bears latency
- **Decision:** Remove per-Turn Recap generation. A locked refresh summarizes successful Turns after a persisted watermark when loading a played Session, running `dnd recap`, or entering `/recap`; the command does not consume a Turn.
- **Consequences:** Normal Turns finish sooner; restore can take a model call; refresh failures preserve the last good Recap.

### D-028: Recap watermark lives on SummaryUpdated / GameState

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 07 / D-022 needs incremental refresh of only successful Turns after the last Recap without a side table that diverges from Event replay.
- **Options considered:**
  - Separate sessions.recap_through_turn column — simple reads; not in the Event log
  - Infer watermark by scanning SummaryUpdated payloads without a field — ambiguous for legacy Events
  - Carry `through_turn` on each `SummaryUpdated` and fold into `GameState.recap_through_turn` — replayable and atomic with the Recap write
- **Decision:** `SummaryUpdated` includes `through_turn`. The Reducer sets `GameState.recap_through_turn` with the summary. Refresh lists successful Turns with `turn_number > recap_through_turn`, then appends one Event advancing both fields.
- **Consequences:** Legacy Recap Events default `through_turn` to 0; equal-text refreshes still write an Event so the watermark advances.

### D-023: Interim explicit-travel short-circuit before full Action Intent

- **Date:** 2026-10-04
- **Status:** superseded by D-024
- **Context:** Ticket 02 needs no-progress Turns for illegal travel before the full fail-closed Action Intent service (ticket 03 / D-020) exists. `move_to` already rejects non-reachable exits, but free-text travel could still reach the DM first.
- **Options considered:**
  - Wait for full Action Intent — cleanest alignment with D-020; leaves travel guardrails incomplete for this ticket
  - Reject only inside `move_to` — state-safe; illegal travel can still be narrated without a Tool call
  - Detect travel verb + unique Location id/name, validate exits, and short-circuit illegal attempts as `no_progress` — covers clear cases now; heuristic until ticket 03
- **Decision:** Use the verb + unique Location heuristic as an interim pre-DM gate for travel only. Legal explicit travel still goes to the DM, which must call `move_to` with a Reachable Destination id. Ticket 03 will supersede this heuristic with structured Action Intent validation.
- **Consequences:** Some non-verb travel phrasing still relies on `move_to` + prompt discipline; ambiguous multi-Location text is not short-circuited.

### D-024: Fail-closed Action Intent gate before DM resolution

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 03 needs unavailable inventory items, surroundings, enemies, and destinations rejected before narration can invent their use. D-023 only covered clear travel phrasing.
- **Options considered:**
  - Expand verb heuristics for every action kind — deterministic; brittle natural language
  - Propose structured Action Intent, validate Playable Fact ids in code, then invoke the DM — fail-closed and testable with model doubles
  - Let Tools alone reject illegal targets — state-safe; illegal use can still be narrated without Tools
- **Decision:** Every Turn proposes an Action Intent (`use` / `interact` / `resolve_enemy` / `travel` / `general`). Code validates referenced ids against inventory, current Location surroundings/enemies, and Reachable Destinations. Invalid, ambiguous, or low-confidence intents become `no_progress` Turns with no Events. Validated intents are injected into the DM prompt. Production uses an LLM proposer; tests may inject stubs or a code proposer that preserves travel detection.
- **Consequences:** Supersedes D-023. DM context always includes validated ids. Intent extraction adds a model call in production unless a code proposer is configured.

### D-025: Typed inventory Tools for take and consumable use

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 04 needs portable Location Items moved into inventory and consumable quantities changed only through replayable Events, without letting the DM invent loot or underflow stacks.
- **Options considered:**
  - Generic `add_item` / quantity patch Tools — flexible; weak validation of source Location and underflow
  - Pure inventory planners plus typed `take_item` / `use_item` Tools emitting `ItemTaken` / `ItemConsumed` — mirrors travel; fail-closed
  - Intent-only quantity changes without Tools — cannot narrate successful take/use while keeping mechanical honesty
- **Decision:** Location `Item` stacks are portable; Interactables are non-portable. `take_item` transfers a nearby stack into inventory. `use_item` validates availability; Items marked `consumable` emit `ItemConsumed` and deduct quantity (removing zero stacks). Illegal take/use returns a Tool error with no Event.
- **Consequences:** Non-consumable use is validation-only (no Event). Scenario/character content must set `consumable` when quantity should change on use.

### D-026: Enemy resolution consumes unused successful Checks this Turn

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 05 / D-021 needs Check-gated Enemy Group damage without trusting narration, and without inventing a combat economy of attack rolls.
- **Options considered:**
  - Any prior Session success unlocks damage — replay-safe but decouples evidence from the current Turn
  - Couple Check skill/reason to a specific enemy id — precise; brittle for POC narration and content
  - Count unused successful `SkillCheckResolved` Events in `events_this_turn` against `EnemyGroupDamaged` Events — Turn-local, deterministic, minimal state
- **Decision:** `resolve_enemy` plans damage only when the Enemy Group is present and undefeated and `successes - damages` for this Turn is at least one. Damage is `min(resolution_damage, current_hp)`; derived remaining/defeated counts come from `EnemyGroup` after updating aggregate HP.
- **Consequences:** Failed Checks cannot fund damage; one success funds one resolution; defeated groups reject further damage and leave available enemy ids.

### D-027: Predicate-driven Objective and Quest completion

- **Date:** 2026-10-04
- **Status:** accepted
- **Context:** Ticket 06 needs Goblin Cave Objectives and the Quest to complete from Location visits, inventory, and Enemy Group defeat without trusting DM narration or Recap text.
- **Options considered:**
  - DM Tool that marks Objectives complete — simple; reintroduces narration as authority
  - Recompute Objective status only in Snapshot views without Events — fast; breaks Event-log audit and replay of completion moments
  - Evaluate predicates after Turn mutations and emit idempotent `ObjectiveCompleted` / `QuestCompleted` Events — authoritative and replayable
- **Decision:** `plan_progress_events` evaluates Scenario predicates against GameState after each Turn. Satisfied active Objectives emit `ObjectiveCompleted` once; when none remain active the Quest emits `QuestCompleted` once. Turn results, SSE `done`, DM context, and CLI show incomplete Objectives, Enemy Group health/counts, and Reachable Destinations.
- **Consequences:** Completion is Turn-batched rather than mid-tool; Quest stays complete on later Turns; Quest predicates beyond Goblin Cave's three types remain future work.

### D-029: Guarded Goblin Cave playthrough is the milestone acceptance bar

- **Date:** 2026-10-05
- **Status:** accepted
- **Context:** Ticket 08 needs one coherent player experience proving D-020–D-028 together: fail-closed intents, travel, inventory, enemy damage, Quest completion, Turn guidance, lazy Recaps, restore, and concurrent Turn/Recap safety. Docs still described per-Turn Recaps and open Quest completion.
- **Options considered:**
  - Ship without a single end-to-end harness — unit coverage already exists; regressions can slip between seams
  - Live-provider smoke only — exercises narration; nondeterministic and slow for CI
  - Deterministic FunctionModel playthrough plus restore/concurrency tests, and update player-facing docs to match D-022 — CI-stable acceptance for the milestone
- **Decision:** Treat the guarded Goblin Cave FunctionModel playthrough (plus mid-play restore and shared-lock Turn/Recap concurrency) as the acceptance bar. README and architecture describe lazy Recaps and authoritative guidance; D-019 remains on record as superseded by D-022.
- **Consequences:** Milestone docs and CI share one narrative of shipped behavior; deeper combat and multi-Scenario Quest predicates stay out of scope.

### D-030: Injectable RNG and Session factories for reproducible runs

- **Date:** 2026-10-05
- **Status:** accepted
- **Context:** Eval and measurement work needs bit-stable Event sequences given the same seed and model outputs. Tools hardcoded `DiceRng`, and `EventStore.create_session` always drew seed/id from `secrets`.
- **Options considered:**
  - Keep hardcoding and only pin seeds in tests via `create_session(rng_seed=…)` — partial; cannot stub dice or Session ids for cassette evals
  - Inject `RngFactory` into TurnDeps and pinable `seed_factory` / `id_factory` on EventStore — full reproducibility seam without changing live defaults
- **Decision:** `RngSource` Protocol + `RngFactory` (default `DiceRng`) on `TurnDeps` / `TurnService`; every rolling Tool uses `ctx.deps.rng_factory`. `EventStore` accepts optional `seed_factory` and `id_factory` (defaults remain `secrets`). Explicit `rng_seed` / `session_id` still override factories. Contract: same seed, same model outputs, same Event payloads (excluding DB timestamps).
- **Consequences:** Later cassette and invariant tickets can pin factories without forking production paths. D-012 seed-advance Events remain the persistence mechanism.

### D-031: Strict model cassettes at the PydanticAI Model boundary

- **Date:** 2026-10-05
- **Status:** accepted
- **Context:** Eval CI must run intent, DM, and Recap model interactions without network or API spend, while live runs can record fixtures. FunctionModel stubs are hand-authored; they do not capture real provider transcripts.
- **Options considered:**
  - Keep FunctionModel-only doubles — CI-stable but cannot golden-replay recorded provider behavior
  - HTTP-level VCR — misses PydanticAI message/tool framing and streaming `request_stream`
  - Wrap `pydantic_ai.models.Model` with strict record/replay per ModelRole — one seam for Agent.run and SSE streaming
- **Decision:** `StrictCassetteModel` wraps an inner Model; modes are `record`, `replay`, and `live`. Replay matches request fingerprints and never calls a live provider (mismatch/exhaustion raise `CassetteError`). Separate Cassette files per ModelRole (`intent` / `dm` / `recap`). Streaming replay synthesizes stream events from the recorded `ModelResponse`.
- **Consequences:** Eval runner (ticket 07) can inject cassette models via existing `TurnService` / `IntentService` / `RecapService` seams. Golden suites store fixtures beside cases.
