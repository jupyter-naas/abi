"""Agent records in the Document Service.

The backend that is shared by every engine process: a record saved through one
is read by the others, and with NATS the Document Service facade carries the
calls to the serving engine. One document per record, named after the agent,
holding the record as ``AgentSpec.model_dump(mode="json")``.

The service passed in is bound to one namespace (a module's own, from its
proxy, or the composer's, from ``for_engine``): records live in its
``agent_specs`` collection, so they never mix with that namespace's other data.
"""

from __future__ import annotations

import re
import threading

from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AGENT_NAME_PATTERN,
    AgentSpec,
    AgentSpecInvalidError,
    AgentSpecNotFoundError,
    IAgentSpecRepository,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionSpec,
    DocumentNotFound,
    VersionConflict,
)
from naas_abi_core.services.document.DocumentService import DocumentService
from pydantic import ValidationError

AGENT_SPEC_NAMESPACE = "naas_abi_core.services.agent_composer"
AGENT_SPEC_COLLECTION = "agent_specs"


class DocumentAgentSpecRepositoryAdapter(IAgentSpecRepository):
    def __init__(
        self, documents: DocumentService, collection: str = AGENT_SPEC_COLLECTION
    ) -> None:
        self._documents = documents
        self._collection = collection
        self._lock = threading.Lock()
        self._ensured = False

    @classmethod
    def for_engine(cls, documents: DocumentService) -> DocumentAgentSpecRepositoryAdapter:
        """Records in the composer's own namespace of the engine's Document Service.

        ``documents`` is the engine root (``engine.services.document``), or an
        already bound view such as a module's, which is used as it is.
        """
        try:
            return cls(documents.for_namespace(AGENT_SPEC_NAMESPACE))
        except PermissionError:
            return cls(documents)

    def _ready(self) -> DocumentService:
        # Declared on first use, not at construction: building a composer must
        # not reach the Document Service (over NATS, the serving engine).
        if not self._ensured:
            with self._lock:
                if not self._ensured:
                    self._documents.ensure_collection(
                        CollectionSpec(name=self._collection)
                    )
                    self._ensured = True
        return self._documents

    @staticmethod
    def _read(name: str, data: dict) -> AgentSpec:
        try:
            spec = AgentSpec.model_validate(data)
        except ValidationError as exc:
            raise AgentSpecInvalidError(name, [str(exc)]) from exc
        if spec.name != name:
            raise AgentSpecInvalidError(
                name, [f"the document declares name '{spec.name}'"]
            )
        return spec

    def get(self, name: str) -> AgentSpec:
        if not re.fullmatch(AGENT_NAME_PATTERN, name):
            raise AgentSpecNotFoundError(name)
        try:
            document = self._ready().get(self._collection, name)
        except DocumentNotFound:
            raise AgentSpecNotFoundError(name) from None
        return self._read(name, document.data)

    def list(self) -> list[AgentSpec]:
        return [
            self._read(document.id, document.data)
            for document in self._ready().iterate(self._collection)
        ]

    def save(self, spec: AgentSpec) -> None:
        self._ready().put(self._collection, spec.name, spec.model_dump(mode="json"))

    def delete(self, name: str) -> None:
        if not re.fullmatch(AGENT_NAME_PATTERN, name):
            raise AgentSpecNotFoundError(name)
        documents = self._ready()
        while True:
            try:
                document = documents.get(self._collection, name)
            except DocumentNotFound:
                raise AgentSpecNotFoundError(name) from None
            try:
                documents.delete(self._collection, name, if_version=document.version)
                return
            except VersionConflict:
                continue  # replaced meanwhile, or gone: look again
