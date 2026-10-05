# 01: Show live Turn progress

**What to build:** During a Turn, the player sees an animated indication of what the system is doing: waiting for the DM, rolling and resolving mechanics, the deterministic result with success or failure, and waiting again until narration starts.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] `dnd play` displays a cycling progress indicator while waiting for the first DM event and between mechanical resolution and narration.
- [x] Dice and Check activity is described in player-facing language rather than raw tool-call output.
- [x] Deterministic roll totals and Check success or failure remain visible as permanent output.
- [x] Progress indicators clear cleanly before narration, errors, and final Turn output without corrupting streamed text.
- [x] The SSE contract and automated tests cover progress phases and their ordering.

## Comments

- Seams: TurnService progress phase order, CLI `consume_turn_stream` / render, POST `/turns` SSE contract.
- Decision: D-018 (`progress` with `awaiting_dm` / `rolling`).
