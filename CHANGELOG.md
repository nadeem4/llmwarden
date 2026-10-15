# Changelog

## 0.1.0 (unreleased)

First version. Everything here is described in `docs/architecture.md`.

- `lw.model(name, api_key=...)` creates a model with its key from a string, a function or a secret reference, and `Model.complete` makes one call with messages or `system` and `user`.
- Three backends behind one contract: `OpenAIBackend` (OpenAI, OpenRouter, Ollama, vLLM, any OpenAI-compatible server), `AnthropicBackend` (beta features pass through), `LiteLLMBackend`. The provider in the model name picks the backend; `backend=` overrides it. `FakeBackend` is public for applications' own tests.
- Secret stores: `env` built in; AWS Secrets Manager, Azure Key Vault, Google Secret Manager and HashiCorp Vault as extras. Values are cached by reference, fetched once under concurrency, re-fetched once on an auth error, and never written or logged.
- Endpoint guard for `public_only` models: https only, public addresses only, the checked address pinned in the transport, no redirects, built from the HTTP library the backend's SDK uses.
- Key hygiene: every error reaches the caller scrubbed with the original dropped; masked `repr`; a logging filter.
- Retries run in llmwarden with every library retry turned off, so every attempt is recorded. Optional fallback model with a shared call id.
- Structured output into a Pydantic class on every backend, natively where the provider supports it and through the prompt where it does not, always validated by llmwarden.
- Observability: tags through a context variable, one `AttemptRecord` per attempt, an in-memory sink and `lw.report`, a function sink, and an OpenTelemetry sink using the GenAI attribute names.
- Prices: the model's own, then the backend's, then a small dated table, else unknown. Unknown is never zero.

Not in this version: streaming, async, embeddings, tool calling.
