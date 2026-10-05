# 08: Verify the complete guarded adventure

**What to build:** A complete Goblin Cave playthrough demonstrates authoritative action guardrails, deterministic enemy damage, Quest completion, next-step guidance, and restore-time Recaps as one coherent player experience.

**Blocked by:** 02: Constrain travel and show reachable destinations; 03: Reject unavailable action targets before DM resolution; 04: Use and transfer authoritative items; 05: Apply deterministic damage to enemy groups; 06: Complete objectives and Quests deterministically; 07: Refresh Recaps only on restore or command.

**Status:** ready-for-agent

- [ ] An end-to-end deterministic playthrough rejects an unavailable item, follows valid exits, acquires and uses an available item, damages every enemy group, completes all objectives, and marks the Quest complete.
- [ ] Each Turn shows accurate remaining objectives, enemy health/counts, and reachable destinations while the DM stays within those facts.
- [ ] Saving and restoring mid-play preserves identical inventory, surroundings, enemy health/counts, objective progress, destinations, and Recap watermark.
- [ ] Concurrent Turn and Recap requests cannot corrupt or lose state.
- [ ] The full test, lint, and type-check suites pass.
- [ ] Architecture, design decisions, glossary, README, changelog, and devlog describe the shipped behavior and supersede the per-Turn Recap decision without rewriting accepted history.
