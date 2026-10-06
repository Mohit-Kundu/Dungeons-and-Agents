# 01: Deterministic run foundation

**What to build:** A run can be reproduced exactly from the same seed and model outputs, including the same domain Event sequence.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Dice dependencies are injected into Turn dependencies and every rolling tool uses the injected source.
- [x] Session seed and identifier generation can be pinned by evals while retaining secure defaults in normal operation.
- [x] A regression test proves identical inputs and model outputs produce identical Event payloads, excluding timestamps.
