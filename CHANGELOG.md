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

### Changed

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
