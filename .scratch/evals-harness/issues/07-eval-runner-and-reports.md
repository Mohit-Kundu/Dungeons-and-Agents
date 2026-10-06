# 07: Eval runner and reports

**What to build:** A single eval command can run the configured model in live, record, or replay mode and produce a useful per-case and aggregate report.

**Blocked by:** 03: Turn telemetry and cost metrics; 06: Adversarial and golden replay suite.

**Status:** ready-for-agent

- [ ] Eval Cases are loaded and executed in isolated Sessions with deterministic seed and cassette selection.
- [ ] `dnd eval run` supports golden, adversarial, and all suites in live, record, and replay modes.
- [ ] Reports include no-progress rate, tool-call validity, narration contradictions, invariant violations, token usage, latency percentiles, and Session cost.
- [ ] Reports are written as machine-readable JSON and concise Markdown, with live evals targeting only the configured model.
