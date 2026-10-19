"""The ports over the SDK's engine services.

The SDK's services are async and the provider is synchronous (authlib is): each
call is scheduled on the module's event loop from the worker thread that runs
the request. Never call them from the loop's own thread, which would wait on
itself: the module builds its service with ``asyncio.to_thread``.

The Document Service namespace is the module's own (``idp``) and the secrets are
named ``idp/...``: the engine seals both to this module's service account.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from typing import Any, TypeVar

from naas_abi_sdk.services.errors import (
    DocumentNotFound,
    UniqueViolation,
    VersionConflict,
)
from naas_abi_sdk.services.models import CollectionSpec as SdkCollectionSpec
from naas_abi_sdk.services.models import FieldSpec

from naas_abi_idp.ports import (
    CollectionSpec,
    Conflict,
    Doc,
    DocumentStore,
    Mail,
    Mailer,
    Page,
    SecretStore,
)

T = TypeVar("T")
TIMEOUT_SECONDS = 30.0


class _Bridge:
    def __init__(self, loop: asyncio.AbstractEventLoop, timeout: float) -> None:
        self._loop, self._timeout = loop, timeout

    def run(self, coro: Awaitable[T]) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(self._timeout)  # type: ignore[arg-type]


class SdkDocumentStore(DocumentStore):
    def __init__(
        self,
        documents: Any,
        loop: asyncio.AbstractEventLoop,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._documents = documents
        self._bridge = _Bridge(loop, timeout)

    def ensure(self, spec: CollectionSpec) -> None:
        fields = {
            name: FieldSpec(name, "string", indexed=True) for name in spec.indexed
        }
        for group in spec.unique:
            for name in group:
                fields.setdefault(name, FieldSpec(name, "string", indexed=True))
        self._bridge.run(
            self._documents.ensure_collection(
                SdkCollectionSpec(
                    name=spec.name,
                    fields=tuple(fields.values()),
                    unique_together=tuple(tuple(g) for g in spec.unique),
                )
            )
        )

    def get(self, collection: str, id: str) -> Doc | None:
        try:
            doc = self._bridge.run(self._documents.get(collection, id))
        except DocumentNotFound:
            return None
        return Doc(doc.id, doc.data, doc.version)

    def create(self, collection: str, id: str, data: Mapping[str, Any]) -> Doc | None:
        try:
            doc = self._bridge.run(
                self._documents.put(collection, id, dict(data), if_version=0)
            )
        except VersionConflict:
            return None
        except UniqueViolation as exc:
            raise Conflict(str(exc)) from exc
        return Doc(doc.id, doc.data, doc.version)

    def replace(self, doc: Doc, collection: str, data: Mapping[str, Any]) -> Doc | None:
        try:
            written = self._bridge.run(
                self._documents.put(
                    collection, doc.id, dict(data), if_version=doc.version
                )
            )
        except (VersionConflict, DocumentNotFound):
            return None
        except UniqueViolation as exc:
            raise Conflict(str(exc)) from exc
        return Doc(written.id, written.data, written.version)

    def delete(self, collection: str, id: str, *, version: int | None = None) -> bool:
        try:
            self._bridge.run(self._documents.delete(collection, id, if_version=version))
        except (VersionConflict, DocumentNotFound):
            return False
        return True

    def find(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> Page:
        page = self._bridge.run(
            self._documents.find(
                collection,
                where=[(k, "eq", v) for k, v in (where or {}).items()],
                limit=limit,
                cursor=after,
            )
        )
        return Page([Doc(d.id, d.data, d.version) for d in page.items], page.cursor)


class SdkSecretStore(SecretStore):
    def __init__(
        self,
        secret: Any,
        loop: asyncio.AbstractEventLoop,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._secret = secret
        self._bridge = _Bridge(loop, timeout)

    def get(self, name: str) -> str | None:
        value = self._bridge.run(self._secret.get(name))
        return None if value is None else str(value)

    def set(self, name: str, value: str) -> None:
        self._bridge.run(self._secret.set(name, value))

    def remove(self, name: str) -> None:
        self._bridge.run(self._secret.remove(name))


class SdkMailer(Mailer):
    """Mail through the engine's email service: the local filesystem adapter in
    ``abi dev up``, SMTP or SES where one is configured."""

    def __init__(
        self,
        email: Any,
        loop: asyncio.AbstractEventLoop,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._email = email
        self._bridge = _Bridge(loop, timeout)

    def send(self, mail: Mail) -> None:
        self._bridge.run(
            self._email.send(
                to_email=mail.to,
                subject=mail.subject,
                text_body=mail.text,
                html_body=mail.html,
                from_email=mail.from_email,
                from_name=mail.from_name,
            )
        )
