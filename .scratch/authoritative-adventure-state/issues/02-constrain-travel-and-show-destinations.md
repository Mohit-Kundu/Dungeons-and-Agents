# 02: Constrain travel and show reachable destinations

**What to build:** A player can travel only through exits declared for the current Location, and after every Turn the game shows the Locations that are currently reachable, including meaningful choices when more than one route is available.

**Blocked by:** 01: Load an authoritative playable world.

**Status:** ready-for-agent

- [ ] Travel accepts stable Location IDs and rejects unknown, current, or non-adjacent destinations without changing Location.
- [ ] A rejected travel attempt is recorded as a no-progress Turn with a deterministic obstacle response.
- [ ] Successful travel emits a replayable Event, updates the current Location, and records that the destination was visited.
- [ ] The Turn result and CLI render every reachable destination from authoritative state rather than DM prose.
- [ ] The DM receives the same destination choices for its next-step nudge and cannot create an off-map route.
- [ ] Automated tests cover valid travel, invalid travel, branching exits, replay, API output, and CLI rendering.
