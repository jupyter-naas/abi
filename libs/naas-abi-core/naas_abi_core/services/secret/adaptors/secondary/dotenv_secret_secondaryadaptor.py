import os
from threading import Lock
from typing import Any

from dotenv import dotenv_values, find_dotenv, set_key, unset_key
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter
from naas_abi_core.utils.Logger import logger


class DotenvSecretSecondaryAdaptor(ISecretAdapter):
    """Secrets in a dotenv file.

    ``read_only`` serves a file another process owns, such as one on a volume
    mounted read-only: ``set`` and ``remove`` leave it alone, so the service
    can still write to its other adapters.

    Reads take the file first, then the process environment.
    ``environment_first`` reverses that, so a variable the deployment sets wins
    over a value saved in the file earlier, as when the config is rendered;
    ``list`` shows the same values for the file's keys.
    """

    def __init__(
        self,
        path: str = ".env",
        read_only: bool = False,
        environment_first: bool = False,
    ):
        self.path = path
        self.read_only = read_only
        self.environment_first = environment_first
        self._lock = Lock()

        if not os.path.exists(self.path):
            raise FileNotFoundError(
                "Dotenv secret adapter is configured to use "
                f"'{self.path}', but this file does not exist. "
                "Please create it or update services.secret.secret_adapters[].config.path."
            )

        logger.debug(f"dotenv is using the file: {self.path}")
        logger.debug(f"dotenv discoverable file is: {find_dotenv()}")

        self.secrets = dotenv_values(self.path)

    def get(self, key: str, default: Any = None) -> str | Any | None:
        with self._lock:
            env_value = os.environ.get(key)
            if self.environment_first and env_value is not None:
                return env_value

            secret_value = self.secrets.get(key)
            if secret_value is not None:
                return str(secret_value)

            if env_value is not None:
                return env_value

        return default

    def set(self, key: str, value: str):
        if self.read_only:
            self._skip_write("set", key)
            return
        with self._lock:
            os.environ[key] = value
            set_key(self.path, key, value)
            self.secrets[key] = value

    def remove(self, key: str):
        if self.read_only:
            self._skip_write("remove", key)
            return
        with self._lock:
            unset_key(self.path, key)
            self.secrets.pop(key, None)
            os.environ.pop(key, None)

    def _skip_write(self, operation: str, key: str) -> None:
        if key in self.secrets:
            # The value in this file still answers reads that no earlier
            # adapter answers.
            logger.warning(
                f"Secret {key} is in the read-only file {self.path}: {operation} "
                "does not change it there."
            )

    def list(self) -> dict[str, str | None]:
        with self._lock:
            secrets: dict[str, str | None] = {}
            for key in self.secrets:
                value = self.secrets.get(key)
                if self.environment_first and key in os.environ:
                    value = os.environ[key]
                secrets[str(key)] = str(value)
            return secrets
