# 01: Load an authoritative playable world

**What to build:** A new or existing Session loads a validated Scenario whose playable facts include stable Locations, directed exits, usable surroundings, enemy-group definitions, and deterministic Quest objective predicates. Existing Sessions upgrade lazily and remain replayable.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Scenario validation rejects duplicate IDs, unknown exit targets, an unknown starting Location, invalid enemy health/count values, and objective predicates that reference missing playable facts.
- [x] Creating a Session seeds the authoritative playable world into replayable state rather than relying on Briefing prose.
- [x] Loading a Session created with the previous schema deterministically supplies the new world state without discarding its existing Events, Turns, or Recap.
- [x] Snapshot rebuild and lazy upgrade produce equivalent GameState.
- [x] Goblin Cave declares its playable Locations, exits, surroundings, enemy groups, and Quest predicates explicitly.
- [x] Automated tests cover valid content, each invalid-reference class, new Sessions, legacy Sessions, and replay.

## Comments

- Seams: Scenario loader validation, Session create Snapshot, lazy upgrade on get/rebuild, Reducer/SessionCreated fold, HTTP state create/get.
- Location field now stores stable IDs (`cave_mouth`); display names remain on world Locations.
