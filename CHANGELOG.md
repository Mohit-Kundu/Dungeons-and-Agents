# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Python package scaffold (`dnd-agent`) with `uv`, Ruff (lint + format), Pyright, and Pytest
- `Settings` loaded from `DND_*` environment variables
- Project logs: `docs/design_choices.md`, `docs/devlog.md`, `GLOSSARY.md`, and this changelog
- Local-markdown issue tickets under `.scratch/poc-foundation/issues/`
- Domain models for Character / GameState / SessionCreated Event
- SQLite EventStore with Snapshot cache and pure Reducer
- Starter content: Brynn Ironfoot + goblin_cave scenario
- FastAPI `POST /sessions`, `GET /sessions/{id}/state`, `GET /sessions/{id}/events`
- CLI commands: `dnd serve`, `dnd new`, `dnd state`, `dnd log`
