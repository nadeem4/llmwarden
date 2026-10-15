# llmwarden

Call any model with any key, fetched safely from wherever you keep secrets, and see exactly where your money goes and which requests fail.

> **Status: 0.1.0 in development.** The core, the three backends, the five secret stores, the endpoint guard, key hygiene, recorded retries, tags, reports and the OpenTelemetry sink are implemented and covered by a contract test suite that runs the same scenarios against every backend. Not on PyPI yet. The design is in [docs/architecture.md](docs/architecture.md), the working rules in [docs/contributing.md](docs/contributing.md), and what shipped in [CHANGELOG.md](CHANGELOG.md).

## The problem

An AI application is rarely one model call. A retrieval pipeline rewrites the question, reranks results and writes the answer. A multi-agent system plans, writes, checks and summarizes. Each part may use a different provider, a different model and a different key.

Calling many providers is a solved problem. What is not solved is everything around the call:

- **Secrets live in many places.** One team keeps keys in environment variables, another in AWS Secrets Manager, Azure Key Vault or HashiCorp Vault. Keys get rotated. Every application writes its own code to fetch them.
- **Custom endpoints are a hole.** If users can type a base URL, a hosted app can be made to send requests, with a key attached, to an internal address or a cloud metadata service.
- **Keys leak.** Provider SDK errors keep the request, the request holds the key, and the traceback ends up in a log.
- **Retries hide cost.** Libraries retry quietly, and the failed attempts never show up in any report.
- **Nobody knows where the money went.** Usage comes back per call, in a different shape for each provider, with nothing linking it to the user, request or feature that caused it.

Every project ends up rewriting the same layer. llmwarden is that layer, written once.

## What it provides

### 1. A model with its key, in one line

```python
import llmwarden as lw

fast = lw.model("groq/llama-3.3-70b-versatile",
                api_key=lw.secret("aws", "prod/llm", field="groq_key"))
strong = lw.model("anthropic/claude-sonnet-5-5",
                  api_key=lw.secret("env", "ANTHROPIC_API_KEY"))

reply = fast.complete(system="Rewrite the question.", user=question)
```

No config file. Create a model in code, give it a key, call it. A model is cheap to create, so a hosted app can build one per request with the end user's own key.

### 2. Secrets from any store, and rotation that just works

- The key can be a plain string, a function that returns one, or a reference: `lw.secret(store, name, field=None)`.
- `env` is built in. AWS Secrets Manager, Azure Key Vault, HashiCorp Vault and Google Secret Manager are optional extras. Register a store once at startup, with its region or address, then refer to secrets by name.
- Write your own store with one method.
- When a key is rotated, `model.refresh()` fetches it again. If a call fails because the key was refused and the key came from a store, llmwarden fetches it again and retries once, so a rotated key works without a restart.
- Fetched keys stay in memory only. They are never written to disk, logs or errors.

### 3. A guard for custom endpoints

With `public_only=True`, meant for hosted apps that strangers use:

- A custom base URL must be `https`.
- Its host must resolve to public addresses only. Private, loopback, link-local and cloud metadata addresses are refused.
- The request goes to the exact address that was checked, so a DNS change between check and call cannot reach a private address.
- Redirects are not followed.
- URLs with credentials, fragments or query tricks are refused.

### 4. Key hygiene

- A key is handed to the client that needs it and to nothing else.
- Every provider error is re-raised as a fresh error with the key scrubbed and the original dropped, so the key cannot appear in a traceback.
- A model prints with its key masked.

### 5. Observability and cost attribution, out of the box

```python
with lw.tags(request="q-1842", customer="acme"):
    plan = planner.complete(..., tags={"agent": "planner"})
    sql = writer.complete(..., tags={"agent": "sql_writer"})

lw.report(group_by=["customer", "agent"])
```

- **Tags** set once where a request comes in apply to every call inside it, however deep. Add more on any call.
- **Every attempt is recorded,** retries included: model, outcome, error kind, tokens, cost, time and tags. Retries happen inside llmwarden, never hidden inside a provider library, so none go uncounted.
- **Reports** add up cost, tokens, failures and time by any tag: per customer, per feature, per agent, per request.
- **OpenTelemetry** spans are emitted for every attempt, using the standard GenAI attribute names, so Grafana, Jaeger, Langfuse, Phoenix, Datadog or any other OpenTelemetry tool can show them with no extra code.
- Unknown prices and token counts are reported as unknown, never as zero.
- Prompts and replies are never recorded. Keys never are.

### 6. Structured output, the same everywhere

Pass a Pydantic class and get back a validated object, on every provider, because llmwarden validates the reply itself. A reply that fails validation is retried like any other failure, and recorded.

### 7. Swappable backends

Three backends ship in the first version, and the same contract test suite runs against each:

| Backend | Reaches | Install |
|---|---|---|
| `OpenAIBackend` | OpenAI, OpenRouter, Ollama, vLLM, any OpenAI-compatible server | `llmwarden[openai]` |
| `AnthropicBackend` | Anthropic, with beta features passed through | `llmwarden[anthropic]` |
| `LiteLLMBackend` | everything LiteLLM lists | `llmwarden[litellm]` |

The provider in the model name picks the backend. Pass `backend=` to override it, or write your own adapter in one file. Retries, records, scrubbing, schema validation and pricing live in llmwarden, so every backend behaves the same.

## What it is not

- **Not another provider client.** Calls go through an existing library behind one small interface. Wherever that library already does something well, llmwarden uses it, and fills in only what is missing.
- **Not a framework.** It does not know about your stages, agents or pipelines. Your code decides which model each part uses.
- **Not a proxy or gateway server.** It is a library inside your application.
- **Not a dashboard.** It emits OpenTelemetry, which the tools you already use can show.

## Not yet

Streaming, async calls, embeddings and tool calling come after the first release, as additions to the same interface.

## Install

```
pip install "llmwarden[openai]"          # one backend
pip install "llmwarden[anthropic,aws]"   # a backend and a secret store
pip install "llmwarden[all]"             # everything
```

Python 3.12 or newer.

## Who it is for

Anyone shipping an application with more than one model call, especially one that is hosted for other people. It starts as the shared layer for two projects, [RAG Playground](https://github.com/nadeem4/rag-playground) and [nl2sql](https://github.com/nadeem4/nl2sql), which each built their own version of it.

## Developing

```
uv sync --group dev
uv run pytest
```

Every test runs without a network connection. See [docs/contributing.md](docs/contributing.md).

## Next steps

1. Release 0.1.0 to PyPI.
2. Move RAG Playground's Pandion package onto it, then nl2sql.
3. Streaming, async and tool calling, as additions to the same interface.
