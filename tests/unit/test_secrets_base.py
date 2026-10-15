import json
import threading
import time

import pytest

from llmwarden.secrets.base import (
    SecretRef,
    SecretStore,
    clear,
    invalidate,
    resolve,
    secret,
    store_for,
    use,
)
from llmwarden.types import SecretNotFound


class CountingStore:
    id = "counting"

    def __init__(self, values, delay=0.0):
        self.values, self.calls, self.delay = values, 0, delay

    def get(self, name):
        self.calls += 1
        time.sleep(self.delay)
        if name not in self.values:
            raise SecretNotFound(self.id, name)
        return self.values[name]


@pytest.fixture(autouse=True)
def _clean():
    clear()
    yield
    clear()


def test_secret_builds_ref_and_repr_hides_nothing_secret():
    ref = secret("env", "MY_KEY", field="f", ttl=10)
    assert ref == SecretRef("env", "MY_KEY", "f", 10)
    assert repr(ref) == "SecretRef(store='env', name='MY_KEY')"


def test_env_store_is_registered_by_default():
    assert store_for(secret("env", "X")).id == "env"


def test_use_registers_and_store_instance_is_accepted_directly():
    s = CountingStore({"a": "1"})
    use(s)
    assert store_for(secret("counting", "a")) is s
    assert store_for(secret(s, "a")) is s
    assert isinstance(s, SecretStore)


def test_resolve_caches_by_store_name_field():
    s = CountingStore({"a": json.dumps({"k1": "v1", "k2": "v2"})})
    use(s)
    assert resolve(secret(s, "a", field="k1")) == "v1"
    assert resolve(secret(s, "a", field="k1")) == "v1"
    assert resolve(secret(s, "a", field="k2")) == "v2"
    assert s.calls == 2


def test_field_on_non_json_or_missing_field_raises_secret_not_found():
    s = CountingStore({"plain": "x", "obj": json.dumps({"a": 1})})
    use(s)
    with pytest.raises(SecretNotFound):
        resolve(secret(s, "plain", field="a"))
    with pytest.raises(SecretNotFound):
        resolve(secret(s, "obj", field="zzz"))


def test_ttl_expires_and_invalidate_forces_refetch():
    s = CountingStore({"a": "1"})
    use(s)
    clock = [100.0]
    ref = secret(s, "a", ttl=5)
    resolve(ref, now=lambda: clock[0])
    resolve(ref, now=lambda: clock[0])
    clock[0] += 6
    resolve(ref, now=lambda: clock[0])
    assert s.calls == 2
    invalidate(ref)
    resolve(ref, now=lambda: clock[0])
    assert s.calls == 3


def test_concurrent_first_fetch_calls_store_once():
    s = CountingStore({"a": "1"}, delay=0.05)
    use(s)
    ref = secret(s, "a")
    results = []
    threads = [threading.Thread(target=lambda: results.append(resolve(ref))) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == ["1"] * 8 and s.calls == 1


def test_unknown_store_id_raises_key_error():
    with pytest.raises(KeyError):
        store_for(secret("nope", "a"))
