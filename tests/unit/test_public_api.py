"""The public surface: names exist, no SDK loads at import, stores are lazy."""

import subprocess
import sys

import llmwarden as lw


def test_public_names_exist():
    for name in [
        "model", "secret", "secrets", "stores", "tags", "report", "observe", "backends",
        "Retry", "Price", "Message", "ChatReply", "Usage", "Cost", "ErrorKind",
        "AttemptRecord", "ProviderError", "InvalidOutput", "NotSupported",
        "ProviderUnavailable", "EndpointRefused", "SecretNotFound", "__version__",
    ]:  # fmt: skip
        assert hasattr(lw, name), name


def test_importing_llmwarden_imports_no_sdk():
    # A fresh interpreter, because this process has already imported the SDKs in other tests.
    code = (
        "import sys, llmwarden\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('openai', 'anthropic', 'litellm', 'boto3', 'hvac', 'opentelemetry', 'azure', 'google')]\n"
        "print(','.join(bad))"
    )
    out = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "", out.stdout


def test_stores_are_lazy():
    assert lw.stores.EnvStore().id == "env"
    assert lw.stores.AwsSecrets.__name__ == "AwsSecrets"
    assert sorted(dir(lw.stores)) == [
        "AwsSecrets", "AzureKeyVault", "EnvStore", "GcpSecretManager", "HashiCorpVault",
    ]  # fmt: skip


def test_default_memory_sink_is_registered():
    from llmwarden.observe import records
    from llmwarden.observe.memory import default_sink

    assert default_sink in records.sinks()
