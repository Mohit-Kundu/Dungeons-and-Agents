# 06: Complete objectives and Quests deterministically

**What to build:** The game evaluates Location, inventory, and enemy predicates after relevant Events, marks objectives and the Quest complete exactly once, and always tells the player what remains to do.

**Blocked by:** 02: Constrain travel and show reachable destinations; 04: Use and transfer authoritative items; 05: Apply deterministic damage to enemy groups.

**Status:** ready-for-agent

- [ ] Objective completion is derived from authoritative predicates and Events rather than a DM claim or Recap text.
- [ ] Location-visited, inventory-contains, and all-enemies-defeated predicates are supported for Goblin Cave.
- [ ] Objective and Quest completion Events are idempotent, replayable, and emitted exactly once.
- [ ] The Quest becomes complete automatically when all required objectives are complete and remains complete on later Turns.
- [ ] Every Turn result displays incomplete objectives, enemy health/counts, and reachable destinations from current state.
- [ ] The DM receives the same authoritative guidance and nudges the player toward one or more valid next choices.
- [ ] Automated tests cover partial progress, each predicate, final completion, repeated evaluation, replay, API output, and CLI rendering.
