# 06: Adversarial and golden replay suite

**What to build:** CI replays representative safe and hostile player actions and verifies that guarded Sessions make progress only through authoritative facts.

**Blocked by:** 02: Strict model cassettes; 04: Event-log invariant audit; 05: Narration contradiction evaluation.

**Status:** ready-for-agent

- [ ] Golden replay covers the complete Goblin Cave playthrough and its expected state transitions.
- [ ] Adversarial replay covers fabricated items, rule-override requests, ambiguous targets, unreachable travel, and prompt injection in Scenario text.
- [ ] Each case asserts `no_progress` or a safe result where appropriate, with allowed and forbidden Event types.
- [ ] The replay suite has no network dependency and fails on invariant violations or narration contradictions.
