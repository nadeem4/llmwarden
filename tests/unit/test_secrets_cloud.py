import json
from types import SimpleNamespace

import pytest

from llmwarden.secrets.base import SecretStore
from llmwarden.types import SecretNotFound


def test_aws_returns_secret_string_and_maps_not_found():
    from llmwarden.secrets.aws import AwsSecrets

    class NotFound(Exception): ...

    class Client:
        exceptions = SimpleNamespace(ResourceNotFoundException=NotFound)

        def get_secret_value(self, SecretId):
            if SecretId == "missing":
                raise NotFound()
            return {"SecretString": json.dumps({"k": "v"})}

    s = AwsSecrets("us-east-1", client=Client())
    assert isinstance(s, SecretStore) and s.id == "aws"
    assert json.loads(s.get("prod/llm")) == {"k": "v"}
    with pytest.raises(SecretNotFound):
        s.get("missing")


def test_aws_binary_only_secret_is_not_found_and_other_errors_pass_through():
    from llmwarden.secrets.aws import AwsSecrets

    class Boom(Exception): ...

    class Client:
        exceptions = SimpleNamespace(ResourceNotFoundException=type("NF", (Exception,), {}))

        def get_secret_value(self, SecretId):
            if SecretId == "binary":
                return {"SecretBinary": b"\x00"}
            raise Boom()

    s = AwsSecrets("us-east-1", client=Client())
    with pytest.raises(SecretNotFound):
        s.get("binary")
    with pytest.raises(Boom):
        s.get("other")


def test_azure_returns_value_and_maps_not_found():
    from llmwarden.secrets.azure import AzureKeyVault

    azure_core = pytest.importorskip("azure.core.exceptions")

    class Client:
        def get_secret(self, name):
            if name == "missing":
                raise azure_core.ResourceNotFoundError("nope")
            return SimpleNamespace(value="v")

    s = AzureKeyVault("https://v.vault.azure.net", client=Client())
    assert isinstance(s, SecretStore)
    assert s.id == "azure" and s.get("k") == "v"
    with pytest.raises(SecretNotFound):
        s.get("missing")


def test_gcp_builds_path_and_decodes_payload():
    from llmwarden.secrets.gcp import GcpSecretManager

    gexc = pytest.importorskip("google.api_core.exceptions")
    seen = {}

    class Client:
        def access_secret_version(self, request):
            seen["name"] = request["name"]
            if "missing" in request["name"]:
                raise gexc.NotFound("nope")
            return SimpleNamespace(payload=SimpleNamespace(data=b"v"))

    s = GcpSecretManager("proj", client=Client())
    assert isinstance(s, SecretStore)
    assert s.id == "gcp" and s.get("k") == "v"
    assert seen["name"] == "projects/proj/secrets/k/versions/latest"
    assert s.get("k/versions/3") == "v" and seen["name"].endswith("/versions/3")
    with pytest.raises(SecretNotFound):
        s.get("missing")


def test_vault_returns_data_as_json_and_maps_invalid_path():
    from llmwarden.secrets.vault import HashiCorpVault

    hvac_exc = pytest.importorskip("hvac.exceptions")

    class KV2:
        def read_secret_version(self, path, mount_point, raise_on_deleted_version=True):
            if path == "missing":
                raise hvac_exc.InvalidPath("nope")
            return {"data": {"data": {"key": "v"}}}

    client = SimpleNamespace(secrets=SimpleNamespace(kv=SimpleNamespace(v2=KV2())))
    s = HashiCorpVault("https://vault.example", client=client)
    assert isinstance(s, SecretStore)
    assert s.id == "vault" and json.loads(s.get("llm/groq")) == {"key": "v"}
    with pytest.raises(SecretNotFound):
        s.get("missing")


def test_not_found_message_names_store_and_name_only():
    from llmwarden.secrets.aws import AwsSecrets

    class NotFound(Exception): ...

    class Client:
        exceptions = SimpleNamespace(ResourceNotFoundException=NotFound)

        def get_secret_value(self, SecretId):
            raise NotFound()

    with pytest.raises(SecretNotFound) as info:
        AwsSecrets("us-east-1", client=Client()).get("prod/llm")
    assert info.value.store == "aws" and info.value.name == "prod/llm"
