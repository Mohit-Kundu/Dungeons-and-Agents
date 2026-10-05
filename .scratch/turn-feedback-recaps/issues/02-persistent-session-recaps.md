# 02: Generate and restore Session recaps

**What to build:** After every completed Turn, the game preserves an LLM-generated recap. When a player inspects or continues an existing Session, they see what has happened so far and the latest player action and DM outcome before proceeding.

**Blocked by:** 01: Show live Turn progress.

**Status:** ready-for-agent

- [ ] Every completed Turn updates a concise recap from the prior recap, completed exchange, and committed mechanical outcomes.
- [ ] Recap updates are immutable Events and survive Snapshot rebuilds.
- [ ] Recap generation uses the configured model without rules tools and exposes its work through the live progress experience.
- [ ] A recap-generation failure preserves the previous recap and does not abort an otherwise successful Turn.
- [ ] `dnd state` displays the persisted recap and clearly labels the latest player action and DM outcome.
- [ ] `dnd play` displays the same Session overview before starting the requested Turn.
- [ ] API, store, CLI, replay, and model-failure behavior are covered by automated tests.

