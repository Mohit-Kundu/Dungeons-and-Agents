# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Live Turn `progress` SSE phases (`awaiting_dm`, `rolling`, `updating_recap`) with player-facing labels
- CLI animated wait indicator (cycling ellipsis) and dramatic Check/Save/roll reveals during `dnd play`
- LLM Session Recap after each Turn via immutable `summary_updated` Events into `GameState.summary`
- `GET /sessions/{id}/overview` and CLI restore view (Recap + latest Turn) on `dnd state` / before `dnd play`
- Ready-for-agent implementation tickets for authoritative Playable Facts, guarded Action Intents, deterministic enemy health and Quest progress, traversal guidance, and lazy Recaps
- Authoritative Scenario PlayableWorld (Locations, exits, surroundings, Enemy Groups, Objectives) seeded into Session Snapshots
- Lazy PlayableWorld upgrade for Sessions created before the world schema
- Graph-constrained `move_to` with reachable destinations on Turn results, SSE `done`, DM context, and CLI
- Deterministic no-progress Turns for illegal explicit travel attempts
- Fail-closed Action Intent gate before DM resolution (use/interact/resolve_enemy/travel/general)
- Typed `take_item` / `use_item` Tools with `ItemTaken` / `ItemConsumed` Events for portable transfer and consumable quantity changes

### Changed

- Goblin Cave Locations use stable ids; `GameState.location` stores the current Location id
- `LocationChanged` also records visited Location ids on PlayableWorld
- D-023 interim travel heuristic superseded by D-024 Action Intent validation
- Pregen fighter rations marked `consumable`; Item model carries an optional consumable flag

### Fixed

## [0.1.0] - 2026-10-04

First playable POC milestone: install, configure a provider, run Goblin Cave, stream Turns, inspect the Event log.

### Added

- Python package scaffold (`dnd-agent`) with `uv`, Ruff, Pyright, and Pytest
- `Settings` from `DND_*` environment variables; `.env.example` for providers and limits
- Project logs: `docs/design_choices.md`, `docs/devlog.md`, `GLOSSARY.md`
- Domain models, SQLite EventStore, pure Reducer, starter Brynn + Goblin Cave content
- FastAPI session/turn API; CLI `serve` / `new` / `state` / `log` / `play`
- Dice, skill Checks, Saves, POC Conditions, short/long rests
- Typed DM Tools; TurnService; SSE Turn stream (`narration_delta`, `tool_call`, `roll`, `state_changed`, `error`, `done`)
- Per-session Turn lock; aborted Turns keep committed Events
- `resolve_model` for Gemini / OpenAI (optional Luna base URL) / Ollama
- Scenario Briefing (intro, locations, beats) seeded into `GameState.summary`
- Opt-in `@pytest.mark.live` provider smokes; FunctionModel POC playthrough test

### Notes

- No combat engine, quest-completion Tool, character creation, multiplayer, or RAG yet (see README roadmap).
