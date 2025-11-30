import base64
from io import StringIO
from typing import Any, Dict

from dotenv import dotenv_values
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter


class Base64Secret(ISecretAdapter):
    def __init__(self, secret_adapter: ISecretAdapter, base64_secret_key: str):
        self.secret_adapter = secret_adapter
        self.base64_secret_key = base64_secret_key

    def __get_base64_secret(self) -> str:
        return str(self.secret_adapter.get(self.base64_secret_key, ""))

    def __get_decoded_secrets(self) -> Dict[str, str | None]:
        base64_secret = self.__get_base64_secret()

        if base64_secret == "":
            return {}

        base64_secret_content = base64.b64decode(base64_secret).decode("utf-8")
        decoded_secrets = dotenv_values(stream=StringIO(base64_secret_content))

        for key, value in decoded_secrets.items():
            decoded_secrets[key] = str(value)

        return decoded_secrets

    def __encode_secrets(self, secrets: Dict[str, str | None]) -> str:
        secret_string = ""
        for key, value in secrets.items():
            secret_string += f'{key}="{value}"\n'
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

    def list(self) -> Dict[str, str | None]:
        return self.__get_decoded_secrets()
