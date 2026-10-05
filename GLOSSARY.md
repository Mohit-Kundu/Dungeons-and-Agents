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

The structured current world and character truth: sheet, inventory, current Location id, quest, conditions, PlayableWorld, and related fields.

Avoid: context (that is prompt material), memory (that is recent turns plus summary).

## PlayableWorld

The authoritative Playable Facts carried on GameState: Locations with exits and surroundings, Enemy Groups, Objectives, and visited Location ids. Seeded from the Scenario at Session create or via lazy upgrade.

Avoid: briefing (prose seed), map (prefer Locations/exits).

## Reachable Destination

A Location currently available through an exit from the party’s Location. Derived from PlayableWorld, never from DM narration.

Avoid: available room (prefer Reachable Destination), adjacent tile.

## Scenario

A predefined starting setup loaded from `content/scenarios/`: starting Location, Quest, linked character id, intro/beats, and authoritative Playable Facts (Locations with exits, surroundings, Enemy Groups, Objectives).

Avoid: adventure module (unless referring to published D&D products), campaign.

## Briefing

The Scenario text seeded into `GameState.summary` at Session creation (intro, known locations, suggested beats, and Scenario notes). Shown by `dnd new` and included in Turn context. After play starts, the rolling Recap replaces this seed in `summary`.

Avoid: prologue (prefer Briefing), system prompt dump.

## Recap

A concise LLM-written summary of what has happened in a Session so far. Stored in `GameState.summary` via immutable `summary_updated` Events. Refreshed lazily on Session restore or an explicit Recap command (not after every Turn). Shown together with the latest Turn.

Avoid: synopsis, campaign journal (narration flavor only), memory (broader than Recap).

## Character

The player’s sheet: abilities, HP, inventory, conditions, and related fields. Distinct from GameState, which also includes current Location, Quest, and PlayableWorld.

Avoid: PC sheet as a separate system name; use Character.

## Playable Fact

An authoritative Scenario or GameState entity that mechanics may reference, such as an inventory item, nearby interactable, enemy group, objective, or exit. Sensory details invented for narration are not Playable Facts.

Avoid: world lore, prompt fact.

## Action Intent

The structured interpretation of a player’s natural-language action, including its action kind and referenced Playable Fact IDs. It must pass deterministic validation before DM resolution.

Avoid: Tool call (the validated intent may lead the DM Agent to call a Tool).

## Enemy Group

A homogeneous set of enemies defined by count and HP per enemy and tracked through aggregate current HP. Remaining count and defeat are derived by code.

Avoid: mob (ambiguous), encounter (broader than the enemies).

## Objective

A deterministic Quest requirement evaluated from Events and GameState, such as visiting a Location, carrying an item, or defeating all required Enemy Groups.

Avoid: suggested beat (narrative guidance is not a completion predicate).
