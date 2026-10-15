"""A hosted app where users bring their own key and can point at their own server.

Needs: pip install "llmwarden[openai]". Nothing runs until a request arrives.

Models are cheap to create, so build one per request with the user's key. With
public_only=True a user-typed base URL must be https and resolve to public
addresses only; the request is pinned to the checked address, redirects are off,
and private, loopback and cloud metadata addresses are refused before any client
is built. Every error reaches you with the key scrubbed out.
"""

import llmwarden as lw


def answer(user_key: str, base_url: str | None, model_name: str, question: str) -> str:
    """Handle one request from one user of a shared deployment."""
    try:
        if base_url:
            model = lw.model(
                f"openai_compatible/{model_name}",
                api_key=user_key or None,  # None sends a placeholder, never a server key
                base_url=base_url,
                public_only=True,
            )
        else:
            model = lw.model(f"openai/{model_name}", api_key=user_key)
    except lw.EndpointRefused as e:
        return f"That endpoint cannot be used here: {e}"

    try:
        with lw.tags(feature="qa"):
            return model.complete(user=question).text
    except lw.ProviderError as e:
        # e.kind is auth, rate_limit, timeout, server, ... and str(e) never holds the key.
        return f"The model call failed ({e.kind.value}): {e}"


if __name__ == "__main__":
    # A local Ollama server is refused under public_only, as it should be on a shared host.
    print(answer("", "http://localhost:11434/v1", "qwen3", "hi"))
    # Running on your own machine, drop public_only and localhost works.
