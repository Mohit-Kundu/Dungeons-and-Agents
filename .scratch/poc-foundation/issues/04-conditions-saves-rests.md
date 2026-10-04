# 04: Add conditions, saving throws, and rests

**What to build:** The player can encounter and recover from common non-combat mechanical effects during play.

**Blocked by:** 03

**Status:** resolved

## Comments

- Seams: rules (saving_throw / conditions / rests), Event/reducer, PydanticAI tools+FunctionModel, POST /turns + CLI play.
- POC conditions: poisoned, frightened, restrained, blinded, prone. Character gains `hit_die`.

- [x] Saving throws use ability modifiers and DCs
- [x] Conditions affect checks according to their defined rules
- [x] Conditions can be added and removed through validated tools
- [x] Short and long rests update HP, hit dice, and applicable conditions
- [x] Invalid operations are rejected without changing state
- [x] The CLI displays condition and rest results
- [x] Rules and API behavior are covered by tests
