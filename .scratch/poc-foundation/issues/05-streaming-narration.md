# 05: Add live streaming narration and visible tool events

**What to build:** Playing feels interactive: narration streams as it is generated while rolls, tool calls, and state changes appear in the CLI.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] The API emits SSE events for narration chunks, tool calls, dice rolls, state changes, errors, and completion
- [ ] The CLI renders streamed narration and mechanical events clearly
- [ ] A per-session lock prevents concurrent turns from corrupting state
- [ ] Aborted turns are recorded without losing or rerolling previous events
- [ ] SSE behavior and concurrency are tested
