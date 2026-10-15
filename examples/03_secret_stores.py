"""Keys from a secret store, with rotation handled for you.

Needs: pip install "llmwarden[openai,aws]" and AWS credentials with read access to
the secret. Swap AwsSecrets for AzureKeyVault, GcpSecretManager or HashiCorpVault.

A store is registered once at startup. Each lw.secret(...) then only names the
secret. The value is fetched once and cached by reference. If the provider rejects
the key, llmwarden fetches it again and retries once, so a rotated key works
without a restart. model.refresh() forces a re-fetch at any time.
"""

import llmwarden as lw

lw.secrets.use(lw.stores.AwsSecrets(region="us-east-1"))

# The secret "prod/llm" holds JSON like {"openai": "sk-...", "groq": "gsk_..."}.
# "field" picks one value out of it.
model = lw.model("openai/gpt-5.4", api_key=lw.secret("aws", "prod/llm", field="openai"))

print(model)  # Model('openai/gpt-5.4', api_key=SecretRef(store='aws', name='prod/llm'))

reply = model.complete(user="Say hello.")
print(reply.text)

# After rotating the key in Secrets Manager:
model.refresh()


# A store of your own is one class with an id and a get method.
class FileStore:
    id = "file"

    def get(self, name: str) -> str:
        with open(f"/run/secrets/{name}", encoding="utf-8") as f:
            return f.read().strip()


lw.secrets.use(FileStore())
local = lw.model("openai/gpt-5.4-mini", api_key=lw.secret("file", "openai_key"))
