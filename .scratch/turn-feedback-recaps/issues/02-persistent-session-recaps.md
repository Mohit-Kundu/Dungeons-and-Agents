# 02: Generate and restore Session recaps

**What to build:** After every completed Turn, the game preserves an LLM-generated recap. When a player inspects or continues an existing Session, they see what has happened so far and the latest player action and DM outcome before proceeding.

**Blocked by:** 01: Show live Turn progress.

**Status:** resolved

- [x] Every completed Turn updates a concise recap from the prior recap, completed exchange, and committed mechanical outcomes.
- [x] Recap updates are immutable Events and survive Snapshot rebuilds.
- [x] Recap generation uses the configured model without rules tools and exposes its work through the live progress experience.
- [x] A recap-generation failure preserves the previous recap and does not abort an otherwise successful Turn.
- [x] `dnd state` displays the persisted recap and clearly labels the latest player action and DM outcome.
- [x] `dnd play` displays the same Session overview before starting the requested Turn.
- [x] API, store, CLI, replay, and model-failure behavior are covered by automated tests.

## Comments

- Seams: Reducer/`SummaryUpdated`, TurnService + `RecapService`, `GET /overview` + CLI restore render.
- Decision: D-019.
