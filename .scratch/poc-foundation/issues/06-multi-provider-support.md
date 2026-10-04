# 06: Support Gemini, OpenAI, and Ollama providers

**What to build:** The same Session can run against the default Gemini provider or a configured OpenAI or Ollama model without changing rules or store logic.

**Blocked by:** 05

**Status:** ready-for-agent

- [ ] Provider and model selection come from environment configuration
- [ ] Gemini is the documented default
- [ ] OpenAI-compatible models, including Luna where available, are supported
- [ ] Ollama is supported as a local option
- [ ] Usage limits, retries, and tool-loop limits prevent runaway calls
- [ ] Provider configuration and failure behavior are tested with mocks
- [ ] Optional live smoke tests are available but never required for the normal test suite
