import os
from typing import Any, Dict

from dotenv import dotenv_values, find_dotenv, set_key
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter
from naas_abi_core.utils.Logger import logger


class DotenvSecretSecondaryAdaptor(ISecretAdapter):
    def __init__(self, path: str = ".env"):
        self.path = path
        logger.debug(f"dotenv is using the file: {self.path}")
        logger.debug(f"dotenv discoverable file is: {find_dotenv()}")

        self.secrets = dotenv_values(self.path)

    def get(self, key: str, default: Any = None) -> str | Any | None:
        secret_value = self.secrets.get(key)
        if secret_value is not None:
            return str(secret_value)

        env_value = os.environ.get(key)
        if env_value is not None:
            return env_value

        return default

    def set(self, key: str, value: str):
        os.environ[key] = value
        set_key(self.path, key, value)

    def remove(self, key: str):
        os.environ.pop(key, None)

    def list(self) -> Dict[str, str | None]:
        secrets: Dict[str, str | None] = {}
        for key in self.secrets.keys():
            secrets[str(key)] = str(self.secrets.get(key))
        return secrets
