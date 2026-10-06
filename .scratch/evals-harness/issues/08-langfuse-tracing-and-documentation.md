# 08: Langfuse tracing and documentation

**What to build:** Opt-in live runs expose per-Turn traces in Langfuse Cloud, and the repository documents the shipped eval and measurement contract.

**Blocked by:** 03: Turn telemetry and cost metrics; 07: Eval runner and reports.

**Status:** ready-for-agent

- [ ] Langfuse tracing is disabled unless credentials are configured and does not affect CI or replay runs.
- [ ] Each Turn is represented as a trace with Session, Turn, intent, status, model, and timing context.
- [ ] Live eval runs initialize tracing and preserve provider errors without hiding them.
- [ ] Architecture, design decisions, glossary, changelog, devlog, and environment examples describe the completed harness.
