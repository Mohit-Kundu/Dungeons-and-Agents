# 03: Reject unavailable action targets before DM resolution

**What to build:** Before the DM resolves free-text input, a fail-closed intent step identifies referenced inventory items, nearby interactables, enemies, and destinations, then rejects unavailable or ambiguous targets without allowing narration to invent their use.

**Blocked by:** 01: Load an authoritative playable world.

**Status:** resolved

- [x] Structured intent distinguishes use, interact, enemy-resolution, travel, and general actions and resolves playable facts to stable IDs.
- [x] Referenced items must be in inventory or explicitly available at the current Location.
- [x] Referenced interactables and enemies must be present and available at the current Location.
- [x] Unknown, unavailable, ambiguous, or low-confidence targets fail closed before invoking the DM.
- [x] A rejected action is recorded as a no-progress Turn with a deterministic explanation and no mechanical Events.
- [x] A validated intent and its allowed IDs are supplied to the DM for resolution.
- [x] Automated tests use deterministic model doubles to cover valid, missing, remote, ambiguous, and uncertain references.

## Comments

- Seams: `validate_action_intent`, TurnService pre-DM gate, IntentService FunctionModel doubles, travel now flows through Action Intent (D-024 supersedes D-023).
- Production API uses LLM IntentService; injected turn models keep CodeIntentService so DM FunctionModels stay isolated.
