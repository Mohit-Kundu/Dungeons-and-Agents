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

## Tool

A typed function the DM Agent may call. Tools run rules, emit Events, and return results. The LLM never writes state directly.

Avoid: function call (when referring to game tools), action (reserved for player intent).

## DM Agent

The LLM-backed Dungeon Master that narrates and chooses Tools. It does not own dice, rules, or state.

Avoid: chatbot, model (when referring to the agent role).

## GameState

The structured current world and character truth: sheet, inventory, location, quest, conditions, and related fields.

Avoid: context (that is prompt material), memory (that is recent turns plus summary).
