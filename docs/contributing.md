# Contributing to llmwarden

Read [architecture.md](architecture.md) first. It is the design, and it names the build order. Work on the current step and nothing ahead of it.

## Rules

- **Test first.** Write the failing test, watch it fail, write the least code that passes, then refactor. No production code without a test that needed it.
- **No test touches the network.** LiteLLM traffic is mocked with `respx`. The openai and anthropic SDKs send through their bundled `httpx2`, which `respx` cannot see: patch `httpx2.HTTPTransport.handle_request` (or inject an `httpx2.MockTransport`) and make the patch raise on any request your script did not expect. Secret store SDKs are mocked at the client. A test that needs a real key is wrong.
- **Keys never leave the call path.** A key goes to `Backend.client()` and nowhere else. Never log it, never put it in an error, never use it as a cache key, never let a test assertion print it on failure.
- **Thin adapters.** A backend translates requests, replies and errors and declares `Capabilities`. It never retries, records, scrubs, validates a schema or prices a call. If you are writing any of those inside `backends/`, stop.
- **One job per module.** Each file in `src/llmwarden/` depends on `types.py` plus what the module table in the architecture names. Do not add a dependency the table does not list.
- **Unknown is `None`.** Usage or cost that was not reported is `None`, never `0`.
- **Do not build ahead.** A reserved field is a reserved field. Streaming, async, embeddings and tools are a later version.
- **Python 3.12 is the floor.** Use `X | None`, not `Optional`; `type X = ...` aliases are fine.
- **No tool attribution.** Commits, PRs, issues, release notes, docs and code carry no "generated with" lines, co-author trailers for tools, or links to them. Authorship is the person who commits.

## Commands

```
uv sync --group dev          # or: pip install -e ".[all]" --group dev
uv run pytest                # must pass before every commit
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

## Commits

Lowercase type prefix and a short summary, as in the existing history: `feat: retry loop records every attempt`, `docs: endpoint guard`. Prefixes in use: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`.

A change that alters behaviour updates the README, `docs/architecture.md` and the module docstring in the same commit.

Diagrams are Mermaid with the black-and-white theme already used in the architecture. No other colours.
