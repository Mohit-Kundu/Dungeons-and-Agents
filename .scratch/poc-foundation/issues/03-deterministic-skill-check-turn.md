# 03: Play a deterministic skill-check turn

**What to build:** A player can enter an action such as “search the room,” and the DM resolves it through a real dice roll and skill check before narrating the result.

**Blocked by:** 02

**Status:** resolved

## Comments

- Seams: dice, skill_check, Event/reducer, PydanticAI tools+FunctionModel, POST /turns + CLI play.

- [x] The DM agent receives current state and recent conversation context
- [x] The agent can call typed state and rules tools
- [x] Skill checks use deterministic code for modifiers, DCs, and dice
- [x] Dice rolls and state changes are persisted as events
- [x] The agent cannot invent a roll or directly mutate state
- [x] A fake/test model verifies tool-call behavior without network access
- [x] The API and CLI expose a complete playable turn
