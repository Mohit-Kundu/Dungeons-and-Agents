# D&D Agent: Architecture & Flow

An LLM-powered Dungeon Master. This document describes the architecture, the high-level turn flow, the POC baseline, and a roadmap of things to add later.

> **Status:** Design phase. No code yet.

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

The LLM acts as the Dungeon Master, but it **never owns the game state**. The LLM narrates and decides intent, while deterministic code owns dice, rules, and state.

Most DM-bot failures (forgotten HP, invented items, fudged rolls) come from letting the model hold state in its context. Keeping state outside the model avoids them.

## How This Solves It

Responsibilities are split by what each part is actually good at:

| Responsibility | Owner | Why |
|---|---|---|
| Narration, tone, NPC voices, interpreting player intent | **LLM** | Creative and language-heavy work is what LLMs are good at. |
| Dice rolls | **Code** (`roll`) | Real randomness, and the result can't be bent to fit the story. |
| HP, inventory, location, quest status | **Code** (state store) | A single source of truth that doesn't drift or get forgotten. |
| Rule resolution (checks, DCs, modifiers, damage) | **Code** (`skill_check`, later a combat engine) | The same inputs always produce the same outcome. |
| Rules and lore lookups | **Retrieval** (later: SRD RAG) | Facts come from a source, not from the model's memory. |

What this changes in practice:

- **State is always accurate.** The model reads it fresh every turn via `get_state()` instead of remembering it.
- **Changes are validated.** The model proposes a change through `update_state(patch)`, and code can reject anything illegal, such as an item the character doesn't own or HP going negative without a death save.
- **Rolls are honest.** The model has to call a tool and use whatever number comes back, so it can't fudge outcomes.
- **Every action is logged.** Each tool call and state change is appended to the event log, which makes sessions replayable, debuggable, and testable.
- **Context stays small.** Only the current state, recent turns, and a summary go into the prompt, so long campaigns don't degrade.
- **Components are swappable.** Because the LLM only narrates and chooses actions, you can change models, add a rules engine, or split into multiple agents without rewriting the game logic.

In short: the LLM is the storyteller, and the code is the rulebook, the dice, and the character sheet.

## POC Baseline (single player, single session)

### Components

1. **Game state store**: one JSON object holding the character sheet, inventory, current location, active quest, NPCs present, and a rolling event log.
2. **Tools** (functions the LLM can call):
   - `roll(dice, reason)`: dice rolls
   - `get_state()` / `update_state(patch)`: read and change state
   - `skill_check(skill, DC)`: combines the modifier from the sheet with a roll
3. **DM agent**: one LLM with a system prompt (DM persona, tone, and rules like "always call tools for rolls, never invent numbers") plus the tools above.
4. **Memory**: the last N turns plus a running summary of earlier ones.
5. **Interface**: a CLI or simple chat loop.

### Turn Flow

```
Player input
   ↓
Load state + recent history + summary
   ↓
DM agent reasons → calls tools as needed
   (skill_check → roll → update_state)  ← loop until done
   ↓
Narrative response to player
   ↓
Append to event log, refresh summary periodically
```

### POC Scope

- One hardcoded pre-made character
- One small starting scenario
- No combat initially (or handle it as plain skill checks)

## Roadmap: What to Add Later

Rough priority order:

1. **Combat engine**: initiative, turn order, attack/damage resolution, conditions. Keep it deterministic code, with the LLM only narrating results.
2. **Rules grounding (RAG)**: index the SRD (spells, monsters, items) so the agent looks things up instead of recalling them.
3. **Long-term memory**: a vector store or structured campaign log for NPCs, past events, and promises made, so the world stays consistent across sessions.
4. **Character creation and leveling**: a guided flow that writes to the character sheet.
5. **Multi-agent split**: separate Narrator, Rules Referee, and NPC roleplayers. A Referee that validates the DM's proposed state changes catches many errors.
6. **World and adventure generation**: a campaign planner that creates locations, factions, and quest hooks ahead of time, with the DM improvising within them.
7. **Multiplayer**: shared state, turn arbitration, and per-player views (secret info, private rolls).
8. **Voice and visuals**: TTS/STT, generated scene art, battle maps.
9. **Persistence and ops**: save/load campaigns, session recaps, logging, and evals (for example, replaying transcripts to check for rule violations or state drift).
10. **Player agency guardrails**: handling off-the-rails inputs, steering back to the story, and difficulty or tone controls.

## Key Design Decisions (decide early)

- **State schema**: get this right first, since everything else depends on it.
- **Who validates changes**: whether the LLM can write state directly or must go through validated tool calls. Validated tool calls are recommended.
- **Framework**: start with a plain tool-calling loop. Move to something like LangGraph only once there are multiple agents or branching flows.

## Next Steps

- [ ] Define the state schema (character sheet, inventory, world, event log)
- [ ] Implement the tool layer (`roll`, `skill_check`, `get_state`, `update_state`)
- [ ] Write the DM system prompt
- [ ] Build the CLI loop and run the first scenario
- [ ] Add running-summary memory
