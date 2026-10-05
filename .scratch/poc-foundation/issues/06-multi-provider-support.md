# 06: Support Gemini, OpenAI, and Ollama providers

**What to build:** The same Session can run against the default Gemini provider or a configured OpenAI or Ollama model without changing rules or store logic.

**Blocked by:** 05

**Status:** resolved

## Comments

- Seams: resolve_model(settings), agent/Turn limits from Settings, mocked provider failure tests, opt-in `@pytest.mark.live` smokes, docs/.env.example.

- [x] Provider and model selection come from environment configuration
- [x] Gemini is the documented default
- [x] OpenAI-compatible models, including Luna where available, are supported
- [x] Ollama is supported as a local option
- [x] Usage limits, retries, and tool-loop limits prevent runaway calls
- [x] Provider configuration and failure behavior are tested with mocks
- [x] Optional live smoke tests are available but never required for the normal test suite
