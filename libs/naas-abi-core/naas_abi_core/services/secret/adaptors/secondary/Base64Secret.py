"""Every secret in one base64 blob, kept under one key of another adapter.

The blob is a JSON object of string keys to string values: a value is stored
and read back literally, never interpolated and never parsed as lines. Blobs
written by older releases in dotenv form are still read, literally (no
``${...}`` interpolation), and the next write stores JSON.
"""

import base64
import json
from io import StringIO
from typing import Any

from dotenv import dotenv_values
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter


def _decode_blob(content: str) -> dict[str, str | None]:
    if content.lstrip().startswith("{"):
        decoded = json.loads(content)
        if not isinstance(decoded, dict):
            raise ValueError("base64 secret blob is not a JSON object")
        return {str(key): str(value) for key, value in decoded.items()}
    # A blob written by an older release: dotenv lines, read literally.
    legacy = dotenv_values(stream=StringIO(content), interpolate=False)
    return {key: str(value) for key, value in legacy.items()}


def _encode_blob(secrets: dict[str, str | None]) -> str:
    content = json.dumps(
        {str(key): str(value) for key, value in secrets.items()},
        ensure_ascii=False,
        sort_keys=True,
    )
    return base64.b64encode(content.encode("utf-8")).decode("utf-8")


class Base64Secret(ISecretAdapter):
    def __init__(self, secret_adapter: ISecretAdapter, base64_secret_key: str):
        self.secret_adapter = secret_adapter
        self.base64_secret_key = base64_secret_key

    def __get_base64_secret(self) -> str:
        return str(self.secret_adapter.get(self.base64_secret_key, ""))

    def __get_decoded_secrets(self) -> dict[str, str | None]:
        base64_secret = self.__get_base64_secret()

        if base64_secret == "":
            return {}

        return _decode_blob(base64.b64decode(base64_secret).decode("utf-8"))

    def get(self, key: str, default: Any = None) -> str | Any | None:
        return self.__get_decoded_secrets().get(key, default)

    def set(self, key: str, value: str):
        decoded_secrets = self.__get_decoded_secrets()

        decoded_secrets[str(key)] = str(value)

        self.secret_adapter.set(self.base64_secret_key, _encode_blob(decoded_secrets))

    def remove(self, key: str):
        decoded_secrets = self.__get_decoded_secrets()
        decoded_secrets.pop(str(key), None)
        self.secret_adapter.set(self.base64_secret_key, _encode_blob(decoded_secrets))

    def list(self) -> dict[str, str | None]:
        return self.__get_decoded_secrets()
