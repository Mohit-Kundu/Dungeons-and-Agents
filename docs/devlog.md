# Devlog

Dated journal. Newest entry first.

---

## 2026-10-04 — Ticket 03 (authoritative-adventure-state): reject unavailable targets

### Done

- Added Proposed/Validated Action Intent models and fail-closed `validate_action_intent`
- TurnService proposes intent before the DM; invalid/ambiguous/uncertain intents become `no_progress` with no Events
- Validated intent ids are injected into the DM prompt; tools still gate mechanical changes
- LLM IntentService for production; CodeIntentService / stubs for deterministic tests
- Superseded D-023 with D-024; 128 tests green

### Broken / surprises

- Sharing the DM FunctionModel with intent extraction steals call turns — keep intent proposers injectable/isolated in tests

### Learned

- Validate ids in code after structured proposal; do not trust the proposer to enforce availability

### Next

- Ticket 04: use and transfer authoritative items
- Ticket 07: refresh Recaps only on restore or command

---

## 2026-10-04 — Ticket 02 (authoritative-adventure-state): constrain travel

### Done

- `validate_travel` / `reachable_destinations` enforce Scenario exits; `move_to` rejects unknown, current, or unreachable targets
- Reducer records visited Location ids on successful travel
- TurnResult and SSE `done` expose reachable destinations; DM prompt and CLI show the same list
- Explicit illegal travel short-circuits as `no_progress` without invoking the DM (D-023)
- 112 tests green

### Broken / surprises

- Travel detection needs a travel verb plus a unique Location name/id so scouting text at the current Location does not false-reject

### Learned

- Keep destination guidance on the Turn completion payload so CLI and API stay aligned without parsing narration

### Next

- Ticket 03: reject unavailable action targets before DM resolution
- Ticket 07: refresh Recaps only on restore or command

---

## 2026-10-04 — Ticket 01 (authoritative-adventure-state): load playable world

### Done

- Extended Scenario YAML/models with Location ids, exits, interactables/items, Enemy Groups, and Objective predicates
- Seeded `PlayableWorld` on `SessionCreated` / GameState; Reducer fold preserves it
- Lazy upgrade maps legacy display-name locations onto ids without discarding Events, Turns, or Recap
- Tests at content, reducer, EventStore, and HTTP session seams; 93 tests green

### Broken / surprises

- `load_scenario` is lru-cached — YAML edits need a fresh process (or cache clear) during iterative local runs

### Learned

- Keep upgrade logic on read/rebuild rather than rewriting the Event log so legacy payloads stay intact

### Next

- Ticket 02: constrain travel and show reachable destinations
- Ticket 07: refresh Recaps only on restore or command

---

## 2026-10-04 — Planning: authoritative adventure state

### Done

- Published eight `ready-for-agent` tracer-bullet tickets with explicit blocking edges
- Chose Scenario-backed Playable Facts, fail-closed Action Intent validation, graph-constrained travel, and deterministic objective completion
- Chose homogeneous Enemy Groups with aggregate HP, code-owned damage deductions/counts, and check-based encounters
- Superseded per-Turn Recaps with incremental refresh on Session restore or explicit command
- Recorded D-020–D-022 and added the new domain vocabulary

### Broken / surprises

- Enemy count alone was insufficient: deterministic completion also needs predefined health and damage semantics
- Natural-language guardrails cannot rely on prompts alone; validation must happen before DM narration

### Learned

- The smallest combat increment is authoritative health and damage over existing Checks, not initiative and action economy
- Tickets 01 and 07 form the initial parallel frontier

### Next

- Ticket 01: load an authoritative playable world
- Ticket 07: refresh Recaps only on restore or command

---

## 2026-10-04 — Ticket 02 (turn-feedback-recaps): persistent Session Recaps

### Done

- `SummaryUpdated` Event + Reducer write into `GameState.summary`; rebuild preserves Recap
- No-tools `RecapService` runs after every Turn; `updating_recap` progress; failures stay non-fatal
- `GET /sessions/{id}/overview` + CLI `state` / pre-`play` show Recap and latest Turn
- D-019; glossary Recap term

### Broken / surprises

- Reusing the DM FunctionModel as the Recap model in older tests is accidental but harmless; inject `RecapService` when call counts matter

### Learned

- Latest action belongs on the turns table; only the rolling Recap needs to be Event-sourced into the Snapshot

### Next

- Combat / quest Tools / richer memory when the next effort starts

---

## 2026-10-04 — Ticket 01 (turn-feedback-recaps): live Turn progress

### Done

- Added `progress` SSE events (`awaiting_dm`, `rolling`) with anticipation-focused labels
- CLI `dnd play` shows animated waits, hides raw tool dumps, and reveals Checks/Saves dramatically
- Tests cover TurnService phase order, CLI consume/render, and API SSE contract
- Recorded D-018

### Broken / surprises

- Rich `Status` must be cleared before streamed narration or it corrupts the line; extracted `consume_turn_stream` to own that lifecycle

### Learned

- Progress belongs in the SSE contract, not only the CLI — labels need skill/DC context from the server

### Next

- Ticket 02: persist LLM Session recaps and show them on `state` / before `play`

---

## 2026-10-04 — Ticket 07: playable POC milestone (0.1.0)

### Done

- Rewrote README: install, provider config, play commands, limitations, roadmap
- Enriched `goblin_cave` with locations/beats/notes; seed briefing into Session `summary`
- FunctionModel playthrough covers Check → move → Condition → long rest → inspect log
- Cut `CHANGELOG.md` `[0.1.0]`; full pytest + ruff + pyright green

### Broken / surprises

- Scenario `intro` existed but was unused until briefing landed on `SessionCreated.summary`

### Learned

- Milestone packaging is mostly README + one honest end-to-end seam test, not more rules code

### Next

- Combat engine / quest Tools / summary compression when the next effort starts

---

## 2026-10-04 — Ticket 06: multi-provider support

### Done

- `resolve_model(settings)` for Gemini / OpenAI (+ base URL) / Ollama
- Settings: `openai_base_url`, `agent_retries`; TurnService uses resolved model + retries
- Mocked provider failure tests; live smokes under `tests/live/` deselected by default
- `.env.example` documents provider strings and limits

### Broken / surprises

- PydanticAI `Agent(retries=N)` lands on `_max_tool_retries` / `_max_output_retries`, not `_retries`
- Normal `pytest` needs `addopts = -m 'not live'` so live tests never gate CI

### Learned

- Keep provider credentials on `DND_*` and inject into provider constructors rather than relying on ambient `GOOGLE_API_KEY` / `OPENAI_API_KEY` alone

### Next

- Ticket 07 (playable POC milestone)

---

## 2026-10-04 — Ticket 05: streaming narration

### Done

- `TurnService.stream_turn` maps PydanticAI stream events → D-005 SSE payloads
- FastAPI `POST /turns` returns `text/event-stream`; app-scoped session locks
- CLI SSE parser + `dnd play` live narration / tool / roll rendering
- Abort keeps committed rolls; concurrency serializes; 52 tests green

### Broken / surprises

- FunctionModel needs `stream_function` for `run_stream_events` (plain `function` is not enough)
- Per-request `TurnService` needs a shared `SessionLockRegistry` (shared dict alone raced on lock creation)

### Learned

- Emit `roll` / `state_changed` from domain Events after `FunctionToolResultEvent`, not from tool args alone

### Next

- Ticket 06 (multi-provider) and/or 07 (playable POC milestone)

---

## 2026-10-04 — Ticket 04: conditions, saves, rests

### Done

- Rules: `saving_throw`, condition catalog/effects, `short_rest` / `long_rest`
- Character `hit_die`; Events + Reducer mutate HP, hit dice, Conditions
- DM tools for saves, add/remove Condition, rests; FunctionModel + API tests
- CLI formats Save/Condition/rest Events; sheet shows hit dice
- 46 tests green; pyright clean

### Broken / surprises

- Auto-fail (blinded Perception) must not advance RNG seed — treat like a no-roll outcome
- ASGI tests still need `app.state.store` set when lifespan does not run

### Learned

- Keep condition effects as a pure aggregator applied inside check/save, not duplicated in tools

### Next

- Ticket 05 (SSE streaming) and/or 06 (multi-provider)

---

## 2026-10-04 — Ticket 03: deterministic skill-check Turn

### Done

- Rules: dice expressions + `skill_check` with proficiency/ability mods
- Events for rolls/Checks/location; Reducer advances `rng_seed`
- PydanticAI DM Agent with typed tools; TurnService persists turns
- API `POST /sessions/{id}/turns`; CLI `dnd play`
- FunctionModel tests (no network); 22 tests green

### Broken / surprises

- `agent.tool(fn, name=...)` typing wants `agent.tool(name=...)(fn)`
- Broad `except` on Turn abort so partial Events stay committed (D-009)

### Learned

- Seed advance via `next_rng_seed` on Events beats replaying call counts

### Next

- Ticket 04 (conditions/saves/rests) and/or 05 (SSE streaming)

---

## 2026-10-04 — Ticket 02: persistent Session

### Done

- Domain models + `SessionCreated` Event; pure Reducer + fold/replay
- SQLite EventStore (sessions/events/snapshots) via aiosqlite
- Content loader for pregen fighter + goblin_cave
- FastAPI session create/state/events; CLI `serve`/`new`/`state`/`log`
- Tests at reducer, store, API, and CLI client seams (11 passing)

### Broken / surprises

- httpx `ASGITransport` does not run FastAPI lifespan → tests inject `app.state.store`
- Starlette `TestClient` warns about httpx deprecation (httpx2)

### Learned

- Keep Snapshot as cache; `fold_events` is the authority check for ticket acceptance

### Next

- Ticket 03: deterministic skill-check Turn with DM Agent tools

---

## 2026-10-04 — Ticket 01 review follow-up

### Done

- Aligned ticket/devlog wording with `GLOSSARY.md` (Session, not “game/campaign”)
- Marked ticket 01 `Status: resolved`
- Added explicit `[tool.ruff.format]` baseline

### Next

- Ticket 02

---

## 2026-10-04 — Ticket 01: project foundation and logs

### Done

- Initialized `dnd-agent` with `uv` (Python 3.12, src layout)
- Added `Settings` via pydantic-settings (`DND_*` env vars) with unit tests
- Scaffolded package modules: `domain`, `rules`, `store`, `agent`, `services`, `api`, `cli`
- Configured Ruff, Pyright, Pytest (including `live` marker)
- Created `CHANGELOG.md`, `GLOSSARY.md`, `docs/design_choices.md` (D-001–D-010), this devlog
- Published POC tickets under `.scratch/poc-foundation/issues/`
- Updated `AGENTS.md` logging rule and pointed domain docs at `design_choices.md`

### Broken / surprises

- `/setup-matt-pocock-skills` is a Cursor chat slash command, not a PowerShell command
- `gh` CLI is not installed on this machine (one reason local markdown tracker was chosen)

### Learned

- For this repo, a growing `design_choices.md` beats per-decision ADR files for speed of capture
- PydanticAI can cover multi-provider needs without a hand-rolled adapter

### Next

- Ticket 02: create and inspect a persistent Session (domain models, SQLite store, session API/CLI)
