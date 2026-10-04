# 02: Create and inspect a persistent session

**What to build:** A player can create a predefined session from the starter scenario and inspect the character’s current state through the API and CLI.

**Blocked by:** 01

**Status:** resolved

- [x] A session can be created from the predefined character and scenario
- [x] Character stats, HP, inventory, location, quest, conditions, and event history are represented with validated models
- [x] SQLite persists the session
- [x] State can be reconstructed from the event log
- [x] CLI commands can create a session and display its state
- [x] Tests verify persistence and event replay

## Comments

- Seams: Reducer, EventStore, HTTP session routes, CLI `new`/`state`/`log`/`serve`.
- Starter content: `content/characters/pregen_fighter.json`, `content/scenarios/goblin_cave.yaml`.
