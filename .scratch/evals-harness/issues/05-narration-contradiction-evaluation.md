# 05: Narration contradiction evaluation

**What to build:** Eval runs detect narration that invents entities or contradicts the authoritative Snapshot, without altering live Turn behavior.

**Blocked by:** 02: Strict model cassettes; 04: Event-log invariant audit.

**Status:** ready-for-agent

- [ ] A deterministic entity scan checks Scenario entities, location presence, and dice-result claims against the Snapshot and Event log.
- [ ] An opt-in LLM judge evaluates narration against the before/after Snapshot and Turn Events.
- [ ] Both checks return structured contradiction findings suitable for reports.
- [ ] Tests cover fabricated items, absent creatures or NPC roles, invalid locations, and contradictory roll claims.
