from abi.services.secret.SecretPorts import ISecretAdapter
from dotenv import load_dotenv
import os
from typing import Any


class DotenvSecretSecondaryAdaptor(ISecretAdapter):
    def __init__(self):
        load_dotenv()

    def get(self, key: str, default: Any = None) -> str:
        return os.getenv(key, default)
