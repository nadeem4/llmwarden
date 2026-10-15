import pytest

from llmwarden.secrets.env import EnvStore
from llmwarden.types import SecretNotFound


def test_reads_environment(monkeypatch):
    monkeypatch.setenv("LW_TEST_KEY", "value")
    assert EnvStore().get("LW_TEST_KEY") == "value"


def test_missing_raises_secret_not_found(monkeypatch):
    monkeypatch.delenv("LW_MISSING", raising=False)
    with pytest.raises(SecretNotFound) as info:
        EnvStore().get("LW_MISSING")
    assert info.value.store == "env" and info.value.name == "LW_MISSING"


def test_dotenv_fills_but_never_overrides(tmp_path, monkeypatch):
    pytest.importorskip("dotenv")
    f = tmp_path / ".env"
    f.write_text("FROM_FILE=file\nALREADY=file\n")
    monkeypatch.delenv("FROM_FILE", raising=False)
    monkeypatch.setenv("ALREADY", "env")
    store = EnvStore(dotenv=f)
    assert store.get("FROM_FILE") == "file"
    assert store.get("ALREADY") == "env"
