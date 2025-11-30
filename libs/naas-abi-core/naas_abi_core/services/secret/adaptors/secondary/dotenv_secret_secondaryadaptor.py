import os
from typing import Any, Dict

from dotenv import dotenv_values, set_key
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter


class DotenvSecretSecondaryAdaptor(ISecretAdapter):
    def __init__(self):
        self.secrets = dotenv_values()

    def get(self, key: str, default: Any = None) -> str:
        return self.secrets.get(key, os.environ.get(key, default))

    def set(self, key: str, value: str):
        os.environ[key] = value
        set_key(".env", key, value)

    def remove(self, key: str):
        os.environ.pop(key, None)

    def list(self) -> Dict[str, str | None]:
        secrets: Dict[str, str | None] = {}
        for key in self.secrets.keys():
            secrets[str(key)] = str(self.secrets.get(key))
        return secrets
