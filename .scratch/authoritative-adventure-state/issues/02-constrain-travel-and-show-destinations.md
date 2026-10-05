# 02: Constrain travel and show reachable destinations

**What to build:** A player can travel only through exits declared for the current Location, and after every Turn the game shows the Locations that are currently reachable, including meaningful choices when more than one route is available.

**Blocked by:** 01: Load an authoritative playable world.

**Status:** resolved

- [x] Travel accepts stable Location IDs and rejects unknown, current, or non-adjacent destinations without changing Location.
- [x] A rejected travel attempt is recorded as a no-progress Turn with a deterministic obstacle response.
- [x] Successful travel emits a replayable Event, updates the current Location, and records that the destination was visited.
- [x] The Turn result and CLI render every reachable destination from authoritative state rather than DM prose.
- [x] The DM receives the same destination choices for its next-step nudge and cannot create an off-map route.
- [x] Automated tests cover valid travel, invalid travel, branching exits, replay, API output, and CLI rendering.

## Comments

- Seams: `world.travel` validation, `move_to` Tool, Reducer visited ids, Turn/DoneEvent reachable list, CLI Reachable row, explicit-travel no-progress short-circuit.
- Explicit travel detection is verb + unique Location name/id; full Action Intent lands in ticket 03 (D-023).
