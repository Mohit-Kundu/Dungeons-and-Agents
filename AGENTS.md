## Agent skills

### Issue tracker

Issues and specs live as markdown under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default mattpocock/skills triage role strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout: root `GLOSSARY.md` and `docs/design_choices.md` when they exist. See `docs/agents/domain.md`.

### Logging

A todo or milestone is not done until the relevant project logs are updated:

1. Update `CHANGELOG.md` (`Unreleased` or the milestone section).
2. Add a dated entry to `docs/devlog.md` (newest first): what was done, what broke, what was learned, what’s next.
3. Append any new or changed decision to `docs/design_choices.md` as a new `D-NNN` entry. Never edit an accepted entry in place; mark it `superseded by D-0xx` and add a replacement.
4. Add any new domain term to `GLOSSARY.md` (definition + synonyms to avoid).

Use glossary vocabulary in tickets, code names, and docs.
