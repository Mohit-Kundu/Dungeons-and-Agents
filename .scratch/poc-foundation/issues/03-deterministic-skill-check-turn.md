# 03: Play a deterministic skill-check turn

**What to build:** A player can enter an action such as “search the room,” and the DM resolves it through a real dice roll and skill check before narrating the result.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] The DM agent receives current state and recent conversation context
- [ ] The agent can call typed state and rules tools
- [ ] Skill checks use deterministic code for modifiers, DCs, and dice
- [ ] Dice rolls and state changes are persisted as events
- [ ] The agent cannot invent a roll or directly mutate state
- [ ] A fake/test model verifies tool-call behavior without network access
- [ ] The API and CLI expose a complete playable turn
