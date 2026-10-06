# 02: Strict model cassettes

**What to build:** CI can run DM, intent, and Recap model interactions from checked-in fixtures without network access or API spend, while live runs can record those interactions.

**Blocked by:** 01: Deterministic run foundation.

**Status:** ready-for-agent

- [ ] Model calls are recordable and replayable at the PydanticAI model boundary for intent, DM, and Recap roles.
- [ ] Replay includes streaming responses and never silently falls back to a live provider.
- [ ] Request mismatches fail with an actionable cassette error, and round-trip record/replay tests pass.
