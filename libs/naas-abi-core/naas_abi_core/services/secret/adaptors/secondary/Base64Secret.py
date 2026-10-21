import base64
import re
from io import StringIO
from typing import Any

from dotenv import dotenv_values
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter

# A key that stays one dotenv key: no space, ``=``, quote, ``#``, ``$`` or line break.
_KEY = re.compile(r"[^\s=\"'#$]+")


class Base64Secret(ISecretAdapter):
    """Secrets kept as one base64 dotenv bundle under a single key of another adapter.

    The bundle is data this class writes, so nothing in it is interpolated: values are
    escaped when written (``"``, ``\\``, line breaks) and read back as they were, and
    ``${NAME}`` stays text.
    """

    def __init__(self, secret_adapter: ISecretAdapter, base64_secret_key: str):
        self.secret_adapter = secret_adapter
        self.base64_secret_key = base64_secret_key

    def __get_base64_secret(self) -> str:
        return str(self.secret_adapter.get(self.base64_secret_key, ""))

    def __get_decoded_secrets(self) -> dict[str, str | None]:
        base64_secret = self.__get_base64_secret()

        if base64_secret == "":
            return {}

        base64_secret_content = base64.b64decode(base64_secret).decode("utf-8")
        decoded_secrets = dotenv_values(
            stream=StringIO(base64_secret_content), interpolate=False
        )

        for key, value in decoded_secrets.items():
            decoded_secrets[key] = str(value)

        return decoded_secrets

    def __encode_secrets(self, secrets: dict[str, str | None]) -> str:
        secret_string = ""
        for key, value in secrets.items():
            if not _KEY.fullmatch(key):
                raise ValueError(f"{key!r} cannot be stored as a secret name")
            escaped = (
                str(value)
                .replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
            )
            secret_string += f'{key}="{escaped}"\n'
        return base64.b64encode(secret_string.encode("utf-8")).decode("utf-8")

    def get(self, key: str, default: Any = None) -> str | Any | None:
        return self.__get_decoded_secrets().get(key, default)

    def set(self, key: str, value: str):
        decoded_secrets = self.__get_decoded_secrets()

        decoded_secrets[str(key)] = str(value)

        self.secret_adapter.set(
            self.base64_secret_key, self.__encode_secrets(decoded_secrets)
        )

    def remove(self, key: str):
        decoded_secrets = self.__get_decoded_secrets()
        decoded_secrets.pop(str(key), None)
        self.secret_adapter.set(
            self.base64_secret_key, self.__encode_secrets(decoded_secrets)
        )

    def list(self) -> dict[str, str | None]:
        return self.__get_decoded_secrets()
