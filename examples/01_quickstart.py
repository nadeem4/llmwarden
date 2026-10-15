"""One model, one call.

Needs: pip install "llmwarden[openai]" and OPENAI_API_KEY in the environment.

The provider in the name picks the backend. With no api_key argument, the key is
read from the provider's standard variable through the built-in env store.
"""

import llmwarden as lw

model = lw.model("openai/gpt-5.4", params={"max_tokens": 200})

reply = model.complete(system="Answer in one sentence.", user="What does a warden do?")

print(reply.text)
print(f"tokens in={reply.usage.input_tokens} out={reply.usage.output_tokens}")
print(f"cost={reply.cost.usd if reply.cost else 'unknown'} attempts={reply.attempts}")
