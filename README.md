# llmwarden

Give every stage of your AI application its own model, provider and key, with secrets fetched safely and never leaked.

> **Status: proposal.** There is no code yet. This README describes what the package will do, so the design can be reviewed before it is built. The design is in [docs/architecture.md](docs/architecture.md).

## The problem

An AI application is rarely one model call. A retrieval pipeline rewrites the question, reranks results and writes the answer. A multi-agent system plans, decomposes, refines and summarizes. Each stage may use a different provider, a different model and a different key: a fast cheap model for rewriting, a strong one for the answer, a local server for anything private.

Calling many providers is a solved problem. What is not solved is everything around the call:

- **Keys end up in config files**, or every stage shares one key because the config has nowhere to put a second one.
- **Secrets live in many places.** One team keeps keys in environment variables, another in AWS Secrets Manager, another in Azure Key Vault or HashiCorp Vault. The application has to know about each one.
- **Custom endpoints are a hole.** If users can type a base URL, a hosted app can be made to send requests, with a key attached, to an internal address or a cloud metadata service.
- **Keys leak.** Provider SDK errors carry the request, the request carries the key, and the traceback ends up in a log.
- **Nobody knows what each stage costs.** Usage is reported per call, in a different shape for each provider.

Every project ends up rewriting the same layer. llmwarden is that layer, written once.

## What it provides

### 1. Settings per stage, with defaults

Each stage names its provider, model, key and endpoint. A stage without its own settings uses `default`.

```yaml
stages:
  default:
    model: anthropic/claude-sonnet-5-5
    api_key: ${env:ANTHROPIC_API_KEY}
  rewrite:
    model: groq/llama-3.3-70b-versatile
    api_key: ${aws:prod/groq-key}
  rerank:
    model: openai_compatible/qwen3-reranker
    base_url: https://models.internal.example.com/v1
    api_key: ${vault:secret/data/reranker#key}
  answer: {}   # uses default
```

### 2. Secrets by reference, from any store

A config never holds a key. It holds a reference, `${provider:path}`, that is resolved when the stage is called.

- Built in: `env` (environment variables and an optional `.env` file).
- Optional extras: `aws` (Secrets Manager), `azure` (Key Vault), `vault` (HashiCorp Vault), `gcp` (Secret Manager).
- Your own: register a secret provider with one function.

Resolved secrets are held in memory only, for a time you choose, and are never written back to config, logs or errors.

### 3. A guard for custom endpoints

With `public_only=True`, which is meant for hosted apps that strangers use:

- A custom base URL must be `https`.
- Its host must resolve to public addresses only. Private, loopback, link-local and cloud metadata addresses are refused, and the check runs on the resolved address, not only the name.
- Redirects are not followed.
- URLs with credentials, fragments or query tricks are refused.
- Error messages never suggest setting a key on the server.

### 4. Key hygiene

- A key is handed to the client that needs it and to nothing else.
- Every provider error is re-raised as a fresh error with the key scrubbed and the original exception chain dropped, so the key cannot appear in a traceback.
- Printing a config masks literal secrets and shows references as written.

### 5. Usage and cost per stage

Every call returns token usage in one shape, tagged with its stage. Cost is worked out from a price table you can override. When a price or a count is unknown, it is reported as unknown, never as zero.

## How it will be used

```python
from llmwarden import Warden

warden = Warden.from_yaml("models.yaml", public_only=False)

reply = warden.complete("rewrite", system="Rewrite the question.", user=question)
print(reply.text, reply.usage)

vectors = warden.embed("embed", texts=pieces)

print(warden.usage.by_stage())   # tokens and cost, per stage
```

The application names its stages. llmwarden resolves each stage's settings and secret, checks the endpoint, makes the call, and reports what it cost.

## What it is not

- **Not another provider client.** Calls go through an existing multi-provider library behind a small backend interface, so the provider list stays current without this package rewriting it. The backend can be swapped.
- **Not a proxy or gateway server.** It is a library inside your application.
- **Not an agent framework.** It does not decide what your stages are or in what order they run.

## Who it is for

Anyone shipping an application with more than one model call, especially one that is hosted for other people. It starts as the shared layer for two projects, [RAG Playground](https://github.com/nadeem4/rag-playground) and [nl2sql](https://github.com/nadeem4/nl2sql), which each built their own version of it.

## Status and next steps

1. Review this proposal and the [architecture](docs/architecture.md).
2. Build the core: stage settings, the `env` secret provider, the endpoint guard, key hygiene and the default backend.
3. Move RAG Playground's Pandion package onto it, then nl2sql.
4. Add the cloud secret providers and the usage report.
