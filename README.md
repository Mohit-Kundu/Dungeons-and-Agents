# Dungeons and Agents

An LLM-powered Dungeon Master where **code owns dice, rules, and GameState**. The model narrates and chooses Tools; it never invents rolls or patches the sheet directly.

> **Status:** Playable POC (`0.1.0`). Single player, one starter Scenario, no combat engine.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An LLM provider key (Gemini by default), or a local Ollama daemon

## Install

```powershell
git clone <this-repo>
cd Dungeons-and-Agents
uv sync
copy .env.example .env
```

Edit `.env` and set at least the key for your chosen model:

```env
DND_MODEL=google-gla:gemini-2.5-flash
DND_GEMINI_API_KEY=your-key-here
```

Other providers (see `.env.example`):

| Provider | Example `DND_MODEL` | Credentials |
|---|---|---|
| Gemini (default) | `google-gla:gemini-2.5-flash` | `DND_GEMINI_API_KEY` |
| OpenAI / Luna | `openai:gpt-4.1-mini` or `openai:luna` | `DND_OPENAI_API_KEY` (+ optional `DND_OPENAI_BASE_URL`) |
| Ollama | `ollama:llama3.2` | `DND_OLLAMA_BASE_URL` (default `http://127.0.0.1:11434/v1`) |

## Play

Two terminals (PowerShell):

```powershell
# Terminal 1 — API
uv run dnd serve

# Terminal 2 — CLI
uv run dnd new
uv run dnd play <session_id> "I search the cave mouth for tracks."
uv run dnd state <session_id>
uv run dnd log <session_id>
```

`dnd new` creates a Session of **Goblin Cave** with Brynn Ironfoot, prints the Briefing, and shows the Snapshot. `dnd state` (and the start of `dnd play`) refresh the Recap if needed, then show it with the latest Turn. `dnd recap` refreshes on demand. `dnd play` streams live progress (waiting / rolling), mechanical reveals, and narration over SSE — Recap work is not part of a normal Turn.

Suggested first loop:

1. Scout the Cave Mouth (Check).
2. Move through the Twisting Tunnel into the Goblin Den (only Reachable Destinations succeed).
3. Take the stolen goods, fight the den goblins with Checks + `resolve_enemy`, and watch Objectives / the Quest complete.
4. Inspect `state` / `log` / `recap`, or restore later — inventory, enemies, objectives, and Recap watermark persist.

## What this POC includes

- Deterministic dice, skill Checks, saving throws, Conditions, short/long rests
- Authoritative PlayableWorld (Locations, exits, items, Enemy Groups, Objectives) with fail-closed Action Intents
- Typed DM Tools that emit append-only Events (SQLite EventStore + Reducer Snapshots)
- Check-gated Enemy Group damage and predicate-driven Quest completion
- FastAPI backend + Typer/Rich CLI
- Live Turn streaming (`progress`, `narration_delta`, `tool_call`, `roll`, `state_changed`, `error`, `done`)
- Lazy Recap refresh on Session restore or explicit command
- Multi-provider model resolution from `DND_*` settings

Domain vocabulary lives in [`GLOSSARY.md`](GLOSSARY.md). Design decisions live in [`docs/design_choices.md`](docs/design_choices.md). Architecture and turn-flow writeup: [`docs/architecture.md`](docs/architecture.md).

## Current limitations

- **No full combat engine** — fights use Checks plus deterministic Enemy Group HP, not initiative or action economy.
- **No character creation / leveling** — one pregen Fighter.
- **No multiplayer**, web UI, RAG rules lookup, or long-term campaign memory.
- **Recap is concise, not a full transcript** — `GameState.summary` starts as the Scenario Briefing and refreshes lazily on restore or `dnd recap` / `/recap`.

## Roadmap (out of scope for 0.1.0)

1. Combat engine (initiative, attacks, damage, combat Conditions)
2. SRD rules grounding (RAG)
3. Long-term memory / campaign log
4. Character creation and leveling
5. Multi-agent split (Narrator / Referee / NPCs)
6. World generation, multiplayer, voice/visuals, evals

## Develop

```powershell
uv run pytest
uv run ruff check src tests
uv run pyright src/dnd_agent
```

Opt-in live provider smokes (hits the network):

```powershell
$env:DND_LIVE_SMOKE=1
uv run pytest -m live
```

## Architecture (short)

```
Player → CLI → FastAPI → TurnService → DM Agent (Tools)
                              ↓
                     EventStore (SQLite)
                              ↓
                     Reducer → Snapshot (GameState)
```

The LLM never writes state. Tools validate, roll, emit Events; the Reducer folds them into the Snapshot the next Turn reads.
