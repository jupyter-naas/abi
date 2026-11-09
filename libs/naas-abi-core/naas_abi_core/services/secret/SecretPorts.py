import re
from abc import ABC, abstractmethod
from typing import Any

# What a secret key may hold: names, paths and dotted ids (``NAAS_API_KEY``,
# ``iam/signing``), nothing a ``.env`` line or an IAM pattern could be bent by.
SECRET_KEY_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+")


class SecretAuthenticationError(Exception):
    pass


class InvalidSecretKey(ValueError):
    """A key with a space, ``=``, ``#``, a control character (a newline) or
    nothing at all. IAM would check it percent-encoded while an adapter writes
    it as is: a ``\n`` becomes ``%0A`` for the check and a new line in ``.env``."""


def checked_key(key: object) -> str:
    """``key`` as a secret key, else ``InvalidSecretKey``."""
    text = key if isinstance(key, str) else ""
    if not SECRET_KEY_PATTERN.fullmatch(text):
        raise InvalidSecretKey(f"Not a secret key: {key!r}")
    return text


class ISecretAdapter(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> str | Any | None:
        raise NotImplementedError()

    @abstractmethod
    def set(self, key: str, value: str):
        raise NotImplementedError()

    @abstractmethod
    def remove(self, key: str):
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> dict[str, str | None]:
        raise NotImplementedError()


class ISecretService(ABC):
    __adapter: list[ISecretAdapter]

    @abstractmethod
    def get(self, key: str, default: Any = None) -> str | Any | None:
        raise NotImplementedError()

    @abstractmethod
    def set(self, key: str, value: str):
        raise NotImplementedError()

    @abstractmethod
    def remove(self, key: str):
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> dict[str, str | None]:
        raise NotImplementedError()
        raise NotImplementedError()
