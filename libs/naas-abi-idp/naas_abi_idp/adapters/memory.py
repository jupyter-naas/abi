"""In-memory adapters: tests, the contract suite, and nothing else.

They keep the semantics the document service gives: create-only puts,
compare-and-set on versions, unique groups, equality finds ordered by id.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Mapping
from typing import Any

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


class MemoryDocumentStore(DocumentStore):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._specs: dict[str, CollectionSpec] = {}
        self._docs: dict[str, dict[str, tuple[dict[str, Any], int]]] = {}

    def ensure(self, spec: CollectionSpec) -> None:
        with self._lock:
            self._specs[spec.name] = spec
            self._docs.setdefault(spec.name, {})

    def get(self, collection: str, id: str) -> Doc | None:
        with self._lock:
            found = self._docs[collection].get(id)
            return None if found is None else Doc(id, copy.deepcopy(found[0]), found[1])

    def create(self, collection: str, id: str, data: Mapping[str, Any]) -> Doc | None:
        with self._lock:
            if id in self._docs[collection]:
                return None
            self._check_unique(collection, id, data)
            self._docs[collection][id] = (copy.deepcopy(dict(data)), 1)
            return Doc(id, copy.deepcopy(dict(data)), 1)

    def replace(self, doc: Doc, collection: str, data: Mapping[str, Any]) -> Doc | None:
        with self._lock:
            found = self._docs[collection].get(doc.id)
            if found is None or found[1] != doc.version:
                return None
            self._check_unique(collection, doc.id, data)
            version = doc.version + 1
            self._docs[collection][doc.id] = (copy.deepcopy(dict(data)), version)
            return Doc(doc.id, copy.deepcopy(dict(data)), version)

    def delete(self, collection: str, id: str, *, version: int | None = None) -> bool:
        with self._lock:
            found = self._docs[collection].get(id)
            if found is None or (version is not None and found[1] != version):
                return False
            del self._docs[collection][id]
            return True

    def find(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        limit: int = 100,
        after: str | None = None,
    ) -> Page:
        with self._lock:
            ids = sorted(self._docs[collection])
            items = []
            for id in ids:
                if after is not None and id <= after:
                    continue
                data, version = self._docs[collection][id]
                if all(data.get(k) == v for k, v in (where or {}).items()):
                    items.append(Doc(id, copy.deepcopy(data), version))
                if len(items) > limit:
                    break
            more = len(items) > limit
            items = items[:limit]
            return Page(items, items[-1].id if more else None)

    def _check_unique(self, collection: str, id: str, data: Mapping[str, Any]) -> None:
        for group in self._specs[collection].unique:
            values = tuple(data.get(f) for f in group)
            for other_id, (other, _) in self._docs[collection].items():
                if other_id != id and tuple(other.get(f) for f in group) == values:
                    raise Conflict(f"{collection}: {', '.join(group)} is taken")


class MemorySecretStore(SecretStore):
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, name: str) -> str | None:
        with self._lock:
            return self._values.get(name)

    def set(self, name: str, value: str) -> None:
        with self._lock:
            self._values[name] = value

    def remove(self, name: str) -> None:
        with self._lock:
            self._values.pop(name, None)


class MemoryMailer(Mailer):
    """Keeps what it is asked to send, newest last."""

    def __init__(self) -> None:
        self.sent: list[Mail] = []
        self.fail = False

    def send(self, mail: Mail) -> None:
        if self.fail:
            raise RuntimeError("mail is down")
        self.sent.append(mail)

    def last_code(self, to: str, length: int = 6) -> str:
        """The digits of the newest mail to ``to`` (a test helper)."""
        import re

        for mail in reversed(self.sent):
            if mail.to == to:
                found = re.search(rf"\b(\d{{{length}}})\b", mail.text)
                if found:
                    return found.group(1)
        raise LookupError(f"no code was sent to {to}")
