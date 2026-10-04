# 02: Create and inspect a persistent session

**What to build:** A player can create a predefined session from the starter scenario and inspect the character’s current state through the API and CLI.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] A session can be created from the predefined character and scenario
- [ ] Character stats, HP, inventory, location, quest, conditions, and event history are represented with validated models
- [ ] SQLite persists the session
- [ ] State can be reconstructed from the event log
- [ ] CLI commands can create a session and display its state
- [ ] Tests verify persistence and event replay
