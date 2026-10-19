"""What the provider needs from the outside, as ports.

The domain (``service.py``) and the OIDC server (``oidc.py``) are synchronous: authlib
is, and the HTTP layer runs them in worker threads. The adapters of these ports
bridge to the SDK's async services (``adapters/``) or keep everything in memory
(``adapters/memory.py``, tests and the contract suite).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class IdPError(Exception):
    """A failure the provider's callers can act on; ``code`` is stable."""

    code = "idp_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.code)


class NotFound(IdPError):
    code = "not_found"


class Conflict(IdPError):
    code = "conflict"


class InvalidArgument(IdPError):
    code = "invalid_argument"


class RateLimited(IdPError):
    code = "rate_limited"

    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many attempts")
        self.retry_after = retry_after


class InvalidCode(IdPError):
    """A sign-in code that does not open anything. Says nothing about why."""

    code = "invalid_code"


@dataclass(frozen=True)
class Doc:
    """A stored document: its id, content and version (for compare-and-set)."""

    id: str
    data: dict[str, Any]
    version: int


@dataclass(frozen=True)
class Page:
    items: list[Doc]
    cursor: str | None = None


@dataclass(frozen=True)
class CollectionSpec:
    name: str
    # Field groups that must be unique across the collection.
    unique: tuple[tuple[str, ...], ...] = ()
    # Fields queried by equality.
    indexed: tuple[str, ...] = ()


class DocumentStore(ABC):
    """JSON documents in collections, with compare-and-set.

    The document is the unit of atomicity: anything that must change together
    (a sign-in challenge and its attempts, a refresh token and its family
    marker) is one document, updated with ``replace``.
    """

    @abstractmethod
    def ensure(self, spec: CollectionSpec) -> None: ...

    @abstractmethod
    def get(self, collection: str, id: str) -> Doc | None: ...

    @abstractmethod
    def create(self, collection: str, id: str, data: Mapping[str, Any]) -> Doc | None:
        """The new document; None when the id exists. Raises ``Conflict`` when a
        unique group of the collection is taken."""

    @abstractmethod
    def replace(self, doc: Doc, collection: str, data: Mapping[str, Any]) -> Doc | None:
        """Replace ``doc`` if it is still at its version; None when it changed or
        is gone. Raises ``Conflict`` when a unique group is taken."""

    @abstractmethod
    def delete(self, collection: str, id: str, *, version: int | None = None) -> bool:
        """Whether this call removed it (with ``version``: only that version)."""

    @abstractmethod
    def find(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> Page:
        """Documents whose fields equal ``where``, by id, ``limit`` at a time;
        follow ``cursor`` until it is None."""


class SecretStore(ABC):
    """The provider's secrets: signing keys and the code key, under ``idp/``."""

    @abstractmethod
    def get(self, name: str) -> str | None: ...

    @abstractmethod
    def set(self, name: str, value: str) -> None: ...

    @abstractmethod
    def remove(self, name: str) -> None: ...


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None
    from_email: str = ""
    from_name: str | None = None


class Mailer(ABC):
    """Sends sign-in mail through the engine's email service."""

    @abstractmethod
    def send(self, mail: Mail) -> None: ...
