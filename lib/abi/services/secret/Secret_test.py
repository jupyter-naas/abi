import pytest
from typing import Any, Dict, List

from abi.services.secret.Secret import Secret
from abi.services.secret.SecretPorts import ISecretAdapter

@pytest.fixture
def TestSecretAdapter():
    class TestSecretAdapter(ISecretAdapter):
        def __init__(self, secrets: Dict[str, str]):
            self.secrets = secrets or {}

        def get(self, key: str, default: Any = None) -> str | Any | None:
            return self.secrets.get(key, default)

        def set(self, key: str, value: str):
            self.secrets[key] = value
        
        def remove(self, key: str):
            self.secrets.pop(key, None)
        
        def list(self) -> Dict[str, str]:
            return self.secrets
    
    return TestSecretAdapter


def test_secret(TestSecretAdapter):
    secret = Secret([
        TestSecretAdapter({
            "hello": "world",
            }),
        TestSecretAdapter({
            "hello": "abi",
            "second": "second",
            }),
    ])
    
    assert secret.get("hello") == "world"
    assert secret.list() == {
        "hello": "world",
        "second": "second",
    }
    
    secret.remove("hello")
    assert secret.get("hello") is None
    assert secret.list() == {
        "second": "second",
    }
    
    secret.remove("second")
    assert secret.list() == {}
    
    secret.set("hello", "world")
    assert secret.get("hello") == "world"
    assert secret.list() == {
        "hello": "world",
    }
    
    