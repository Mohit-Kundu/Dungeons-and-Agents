# 05: Apply deterministic damage to enemy groups

**What to build:** Check-based encounters use Scenario-defined enemy health and damage. Code applies damage to homogeneous enemy groups, derives remaining enemy count, and decides when every enemy is defeated without trusting DM narration.

**Blocked by:** 01: Load an authoritative playable world; 03: Reject unavailable action targets before DM resolution.

**Status:** done

- [x] Each enemy group declares a total count, HP per enemy, and deterministic damage applied by a qualifying successful resolution.
- [x] Runtime state stores aggregate current HP and derives remaining count consistently from the homogeneous group definition.
- [x] Enemy resolution requires a valid, present enemy-group ID and qualifying mechanical evidence from the current Turn.
- [x] Damage deductions are deterministic, replayable, and clamp the final result at zero without negative HP or count underflow.
- [x] A defeated enemy group cannot take further damage or be resolved twice.
- [x] Turn output exposes current/max aggregate HP, defeated count, and remaining count from authoritative state.
- [x] Automated tests cover failed and successful Checks, repeated damage, enemy-count thresholds, final defeat, invalid targets, replay, and all-enemies-defeated detection.
