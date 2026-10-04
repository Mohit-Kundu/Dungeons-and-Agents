# Devlog

Dated journal. Newest entry first.

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
