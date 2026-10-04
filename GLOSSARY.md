# Glossary

Domain vocabulary for Dungeons and Agents. Prefer these terms in code, tickets, and docs. Avoid the synonyms listed under each entry.

## Session

One playthrough of a scenario for a player, with its own event log and state snapshot.

Avoid: game, campaign save (unless referring to multi-session campaigns later).

## Turn

One player action plus the DM response that follows, including any tool calls made while resolving it.

Avoid: round (reserved for combat later), message exchange.

## Event

An immutable record of something that happened during a Session (a dice roll, HP change, item gained, and so on). Events are appended to the log and never edited.

Avoid: mutation, patch, update.

## Snapshot

The current `GameState` derived by replaying Events through the Reducer. Cached for fast reads; the Event log remains the source of truth.

Avoid: save file (the log is authoritative).

## Reducer

A pure function that applies an Event to a `GameState` and returns the next state. No I/O.

Avoid: mutator, updater.

## Check

An ability or skill check: roll a d20 (with advantage or disadvantage when applicable), add modifiers, and compare to a DC.

Avoid: ability test, skill roll (prefer "skill check").

## Save

A saving throw against an ability (for example, Constitution). Same dice flow as a Check, different purpose.

Avoid: saving check.

## DC

Difficulty Class. The target number a Check or Save must meet or beat.

Avoid: difficulty, threshold (unless explaining DC to a player in narration).

## Condition

A named mechanical status with defined rules effects (for example, poisoned, frightened). Stored on the character and applied by the rules engine.

Avoid: status effect, buff/debuff as primary terms.

## Hit Die

The class die used when spending Hit Dice on a short rest (for example, a Fighter’s d10). Stored as `hit_die` on Character with `hit_dice_total` / `hit_dice_remaining` counts.

Avoid: health die, HD pool (prefer “hit dice remaining”).

## Short Rest

A brief rest where the Character may spend Hit Dice to recover HP. Does not clear POC Conditions by itself.

Avoid: camp break (unless narrating fiction).

## Long Rest

An extended rest that restores HP to maximum, recovers Hit Dice (up to half the total, rounded up), and clears tracked Conditions.

Avoid: full heal (too vague; prefer Long Rest).

## Tool

A typed function the DM Agent may call. Tools run rules, emit Events, and return results. The LLM never writes state directly.

Avoid: function call (when referring to game tools), action (reserved for player intent).

## DM Agent

The LLM-backed Dungeon Master that narrates and chooses Tools. It does not own dice, rules, or state.

Avoid: chatbot, model (when referring to the agent role).

## GameState

The structured current world and character truth: sheet, inventory, location, quest, conditions, and related fields.

Avoid: context (that is prompt material), memory (that is recent turns plus summary).

## Scenario

A predefined starting setup (location, quest, linked character id, intro text) loaded from `content/scenarios/`.

Avoid: adventure module (unless referring to published D&D products), campaign.

## Character

The player’s sheet: abilities, HP, inventory, conditions, and related fields. Distinct from GameState, which also includes location and quest.

Avoid: PC sheet as a separate system name; use Character.
