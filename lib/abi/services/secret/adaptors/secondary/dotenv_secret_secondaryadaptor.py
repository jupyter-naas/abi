from abi.services.secret.SecretPorts import ISecretAdapter
from dotenv import load_dotenv
import os
from typing import Any, Dict


class DotenvSecretSecondaryAdaptor(ISecretAdapter):
    def __init__(self):
        load_dotenv()

    def get(self, key: str, default: Any = None) -> str:
        return os.getenv(key, default)

    def set(self, key: str, value: str):
        os.environ[key] = value

    def remove(self, key: str):
        os.environ.pop(key, None)

    def list(self) -> Dict[str, str | None]:
        secrets: Dict[str, str | None] = {}
        for key in os.environ.keys():
            secrets[str(key)] = str(os.getenv(key))
        return secrets
