# 05: Add live streaming narration and visible tool events

**What to build:** Playing feels interactive: narration streams as it is generated while rolls, tool calls, and state changes appear in the CLI.

**Blocked by:** 03

**Status:** resolved

## Comments

- Seams: TurnService stream + session lock, POST /turns SSE, CLI SSE client + play, concurrency/abort tests.
- SSE types (D-005): narration_delta, tool_call, roll, state_changed, error, done.

- [x] The API emits SSE events for narration chunks, tool calls, dice rolls, state changes, errors, and completion
- [x] The CLI renders streamed narration and mechanical events clearly
- [x] A per-session lock prevents concurrent turns from corrupting state
- [x] Aborted turns are recorded without losing or rerolling previous events
- [x] SSE behavior and concurrency are tested
