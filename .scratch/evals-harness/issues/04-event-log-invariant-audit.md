# 04: Event-log invariant audit

**What to build:** An independent audit can inspect any Session Event log and report whether authoritative state and progression rules were preserved.

**Blocked by:** 01: Deterministic run foundation.

**Status:** ready-for-agent

- [ ] The audit checks Character and Enemy Group HP bounds, non-negative inventory quantities, and Scenario-defined inventory ids.
- [ ] The audit checks that travel follows exits and Objective or Quest completion occurs only when its predicates hold.
- [ ] Dice Events are checked against the persisted RNG chain.
- [ ] Property-based and focused violation tests cover each invariant.
- [ ] `dnd eval audit` can run the audit against a stored Session.
