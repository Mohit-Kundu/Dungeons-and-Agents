# Devlog

Dated journal. Newest entry first.

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
