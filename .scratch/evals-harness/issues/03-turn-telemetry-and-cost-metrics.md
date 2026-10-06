# 03: Turn telemetry and cost metrics

**What to build:** Every completed Turn has queryable telemetry for model usage, timing, tool validity, and estimated cost, and eval runs can aggregate it.

**Blocked by:** 02: Strict model cassettes.

**Status:** ready-for-agent

- [ ] Telemetry captures model role, model name, request latency, input/output tokens, tool calls, tool errors, and estimated USD cost.
- [ ] Per-Turn telemetry is stored separately from domain Events and survives normal Session persistence.
- [ ] Unknown model pricing is represented explicitly rather than guessed, and unit tests cover metric aggregation.
