# D&D Agent: Architecture & Flow

An LLM-powered Dungeon Master. This document preserves the original architecture reasoning and updates the shipped turn flow for the authoritative-adventure-state milestone.

> **Note:** The playable POC has shipped (`0.1.0`). For install/run instructions see [`README.md`](../README.md). Implemented decisions live in [`design_choices.md`](design_choices.md).

## The Problem with Most Existing Systems

Most LLM-based D&D bots and "AI Dungeon Master" setups put everything in the model's context window: the character sheet, inventory, HP, world facts, and the dice themselves. The model is expected to remember it all and play fair. This is the root cause of the failures players keep running into:

| Failure | Why it happens |
|---|---|
| **Forgotten or drifting HP** | State lives in prose. After a few dozen turns the model loses track or recomputes it wrong. |
| **Invented items and abilities** | Nothing stops the model from granting a "+3 sword" or letting a character cast a spell they don't have. |
| **Fudged or fake rolls** | LLMs can't generate true randomness. They produce plausible-looking numbers and tend to favor the narratively convenient outcome. |
| **Inconsistent rules** | Rules are recalled from training data, so they're applied differently from turn to turn, or hallucinated outright. |
| **Context loss over long sessions** | Early facts (NPC names, promises, quest details) get truncated or summarized away, and the world stops being consistent. |
| **No audit trail** | When something goes wrong, there's no record of what changed or why, so it can't be debugged or tested. |

The core issue is that an LLM is a good storyteller but an unreliable database, calculator, and random number generator. Existing systems ask it to be all three.

## Core Idea

The LLM acts as the Dungeon Master, but it **never owns the game state**. The LLM narrates and chooses Tools; deterministic code owns dice, rules, Playable Facts, and GameState.

Most DM-bot failures (forgotten HP, invented items, fudged rolls) come from letting the model hold state in its context. Keeping state outside the model avoids them.

## How This Solves It

Responsibilities are split by what each part is actually good at:

| Responsibility | Owner | Why |
|---|---|---|
| Narration, tone, NPC voices | **LLM** | Creative and language-heavy work is what LLMs are good at. |
| Dice rolls | **Code** (`RngSource` via Check Tools) | Real randomness; results cannot be bent to fit the story. Seeded and injectable for reproducible evals. |
| HP, inventory, Location, Quest, Enemy Groups | **Code** (EventStore + Reducer) | A single source of truth that does not drift. |
| Action availability | **Code** (Action Intent gate + typed Tools) | Unavailable items, exits, and enemies are rejected before narration invents them. |
| Rule resolution (Checks, DCs, damage) | **Code** | The same inputs always produce the same outcome. |
| Rules and lore lookups | **Retrieval** (later: SRD RAG) | Facts come from a source, not from the model's memory. |

What this changes in practice:

- **State is always accurate.** Each Turn loads a fresh Snapshot rather than trusting model memory.
- **Changes are validated.** Tools and the Action Intent gate reject illegal targets; the DM cannot patch GameState directly.
- **Rolls are honest.** The model must call a Tool and use the returned number.
- **Every mutation is logged.** Events make Sessions replayable, debuggable, and testable.
- **Context stays small.** Snapshot JSON, recent Turns, guidance lists, and a lazy Recap go into the prompt.
- **Components are swappable.** Because the LLM only narrates and chooses Tools, models and rules engines can change without rewriting game logic.

In short: the LLM is the storyteller, and the code is the rulebook, the dice, and the character sheet.

## Shipped POC (single player, Goblin Cave)

### Components

1. **EventStore + Reducer**: append-only SQLite Event log with cached GameState Snapshots (Character, inventory, Location, Quest, PlayableWorld, Recap watermark).
2. **Typed Tools** the DM may call: `skill_check`, `saving_throw`, `add_condition`, rests, `move_to`, `take_item`, `use_item`, `resolve_enemy`. Each Tool validates against Playable Facts and emits Events — never a generic state patch.
3. **Action Intent gate**: before the DM runs, code proposes/validates a structured intent (`use` / `interact` / `resolve_enemy` / `travel` / `general`) against inventory, surroundings, enemies, and Reachable Destinations. Invalid intents become `no_progress` Turns with no Events.
4. **DM agent**: narrates within injected guidance (incomplete Objectives, Enemy Group HP/counts, Reachable Destinations) and the validated Action Intent.
5. **Lazy Recap**: `RecapRefreshService` folds successful Turns after `recap_through_turn` on Session restore or an explicit Recap command — not after every Turn. Shared Session locks serialize concurrent Turn and Recap work.
6. **Interface**: FastAPI (SSE Turns) + Typer/Rich CLI.
7. **Model cassettes (evals)**: `StrictCassetteModel` records/replays intent, DM, and Recap at the PydanticAI Model boundary so CI can run without a live provider (D-031).

### Turn Flow

```
Player input
   ↓
Load Snapshot + recent Turns + Recap
   ↓
Propose Action Intent → validate Playable Facts
   ↓ (reject → no_progress Turn, stop)
DM agent narrates → calls typed Tools as needed
   (Checks / travel / inventory / enemy damage)  ← loop until done
   ↓
Append Turn; evaluate Objective/Quest predicates → Events
   ↓
Return narration + guidance (objectives, enemies, destinations)
```

Recap refresh is a separate locked operation on restore / `dnd recap` / `/recap`.

### POC Scope

- One pregen Fighter (Brynn) and Goblin Cave Scenario with authoritative Locations, exits, items, Enemy Groups, and Objective predicates
- Check-based Enemy Group damage (no initiative / action economy)
- Deterministic Quest completion from predicates
- Guarded playthrough verified end-to-end (reject unavailable targets, travel, take/use, defeat, complete Quest, restore, concurrent Recap)

## Roadmap: What to Add Later

Rough priority order:

1. **Combat engine**: initiative, turn order, attack/damage resolution, combat Conditions. Keep it deterministic code, with the LLM only narrating results.
2. **Rules grounding (RAG)**: index the SRD (spells, monsters, items) so the agent looks them up instead of recalling them.
3. **Long-term memory**: a vector store or structured campaign log for NPCs, past events, and promises made.
4. **Character creation and leveling**: a guided flow that writes to the Character sheet.
5. **Multi-agent split**: separate Narrator, Rules Referee, and NPC roleplayers.
6. **World and adventure generation**: a campaign planner that creates locations, factions, and quest hooks ahead of time.
7. **Multiplayer**: shared state, turn arbitration, and per-player views.
8. **Voice and visuals**: TTS/STT, generated scene art, battle maps.
9. **Ops and evals**: richer campaign persistence, logging, transcript replay for rule violations or state drift.
10. **Tone / difficulty controls**: steering beyond the current Action Intent gate.

## Key Design Decisions

Accepted decisions live in [`design_choices.md`](design_choices.md). The authoritative-adventure-state milestone centers on D-020–D-028 (Playable Facts, fail-closed intents, typed inventory/enemy Tools, predicate Quest completion, lazy Recaps) and D-029 (end-to-end guarded Goblin Cave verification).
