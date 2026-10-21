import inspect
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any

from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
    Document,
    DocumentNotFound,
    IDocumentAdapter,
    OrderBy,
    Page,
    Predicate,
    Value,
    validate_data,
    validate_max_bytes,
    validate_name,
    validate_query,
    validate_version,
)
from naas_abi_core.services.document.iam_catalog import (
    CATALOG,
    COLLECTION,
    DOCUMENT,
    NAMESPACE,
)
from naas_abi_core.services.iam.enforcement import ResourceGuard
from naas_abi_core.services.ServiceBase import ServiceBase


def _max_bytes(find: Callable[..., Any], max_bytes: int | None) -> dict[str, int]:
    """A byte budget, for an adapter whose ``find`` takes one: an adapter
    written before the keyword answers unbounded pages, which the NATS primary
    still sends whole (RPC overflow)."""
    if max_bytes is None:
        return {}
    parameters = inspect.signature(find).parameters
    if "max_bytes" not in parameters and not any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    ):
        return {}
    return {"max_bytes": max_bytes}


class DocumentService(ServiceBase):
    """Namespace-bound collections. One document is the unit of atomicity.

    put replaces the complete document. if_version=None is unconditional,
    zero is create-only, and a positive version is compare-and-swap. Bulk
    helpers can commit a prefix before an error; they are not transactions.

    Two adapter-specific caveats do not change results but can change timing
    or query plans across backends: the PostgreSQL adapter takes a catalog
    row lock on every operation (reads included) to coordinate with
    concurrent declaration/drop changes, while the SQLite adapter does not;
    and an `indexed=True` string/bytes field is fully index-backed for
    ORDER BY on PostgreSQL only up to a 256-character prefix (SQLite indexes
    the full value), so PostgreSQL can fall back to an in-memory sort for
    fields that commonly share a long prefix.

    Wired into an engine, every operation is authorized on
    ``namespace/<ns>``, ``collection/<ns>/<c>`` or ``document/<ns>/<c>/<id>``
    (RFC §6.4), for whoever calls, in process or over NATS: the namespace a
    view is bound to is a name like any other, which the caller's policies
    must cover. A collection the caller may not see is ``CollectionNotFound``,
    a document ``DocumentNotFound``. Namespace administration (``Namespaces``,
    ``EnsureCollection``, ``DropCollection``) is granted by policy, to no
    identity implicitly; the built-in IdP's namespace is sealed to it.
    """

    def __init__(self, adapter: IDocumentAdapter, namespace: str):
        super().__init__()
        self.__adapter = adapter
        self.__namespace = validate_name(namespace)
        self.__can_bind_namespaces = False
        self._guard = ResourceGuard.of(CATALOG, self)

    def __collection(self, action: str, collection: str) -> None:
        self._guard.require(
            action,
            COLLECTION,
            [self.namespace, collection],
            not_found=lambda: CollectionNotFound(
                f"Collection {self.namespace}/{collection} not found"
            ),
        )

    def __document(self, action: str, collection: str, id: str) -> None:
        self._guard.require(
            action,
            DOCUMENT,
            [self.namespace, collection, id],
            not_found=lambda: DocumentNotFound(
                f"Document {self.namespace}/{collection}/{id} not found"
            ),
        )

    @classmethod
    def _for_engine(cls, adapter: IDocumentAdapter) -> "DocumentService":
        root = cls(adapter, namespace="__engine__")
        root.__can_bind_namespaces = True
        return root

    @property
    def adapter(self) -> IDocumentAdapter:
        return self.__adapter

    @property
    def namespace(self) -> str:
        if self.__can_bind_namespaces:
            raise PermissionError("The engine document root only binds namespaces")
        return self.__namespace

    def for_namespace(self, namespace: str) -> "DocumentService":
        """A view bound to ``namespace``; only the engine root can create one.

        Module proxies bind their own module's namespace; ``document_admin``
        binds any. Binding grants nothing: every call on the view is
        authorized for its caller.
        """
        if not self.__can_bind_namespaces:
            raise PermissionError("A bound document service cannot change namespace")
        scoped = DocumentService(self.__adapter, namespace)
        if self.services_wired:
            scoped.set_services(self.services)
        return scoped

    def _for_namespace(self, namespace: str) -> "DocumentService":
        """Composition-root hook kept for existing callers; see ``for_namespace``."""
        return self.for_namespace(namespace)

    def namespaces(self) -> list[str]:
        """Namespaces holding at least one collection that the caller may list;
        engine root only."""
        if not self.__can_bind_namespaces:
            raise PermissionError("A bound document service cannot list namespaces")
        return self._guard.filter(
            "Namespaces", NAMESPACE, self.__adapter.namespaces(), lambda ns: [ns]
        )

    def ensure_collection(self, spec: CollectionSpec) -> None:
        """Declare a collection; a create (RFC §4.4): a new namespace is
        placed in the call's target workspace, or on the platform."""
        namespace = self.namespace
        name = validate_name(spec.name)
        commit = self._guard.create(
            "EnsureCollection",
            COLLECTION,
            [namespace, name],
            container=(NAMESPACE, [namespace]),
            exists=lambda: name in self.__adapter.collections(namespace),
            container_exists=lambda: namespace in self.__adapter.namespaces(),
            not_found=lambda: CollectionNotFound(
                f"Collection {namespace}/{name} not found"
            ),
        )
        self.__adapter.ensure_collection(namespace, spec)
        commit()

    def drop_collection(self, collection: str) -> None:
        collection = validate_name(collection)
        self.__collection("DropCollection", collection)
        self.__adapter.drop_collection(self.namespace, collection)

    def collections(self) -> list[str]:
        """The namespace's collections the caller may list; none when it may
        not see the namespace (RFC §5.5)."""
        namespace = self.namespace
        try:
            self._guard.require_visible(
                NAMESPACE, [namespace], not_found=lambda: CollectionNotFound(namespace)
            )
        except CollectionNotFound:
            return []
        return self._guard.filter(
            "Collections",
            COLLECTION,
            self.__adapter.collections(namespace),
            lambda name: [namespace, name],
        )

    def collection_spec(self, collection: str) -> CollectionSpec:
        """Declared fields and unique groups. Raises ``CollectionNotFound``."""
        self.__collection("CollectionSpec", validate_name(collection))
        return self.__adapter.collection_spec(self.namespace, validate_name(collection))

    def put(
        self,
        collection: str,
        id: str,
        data: dict[str, Value],
        *,
        if_version: int | None = None,
    ) -> Document:
        validate_data(data)
        validate_version(if_version)
        self.__document("Put", validate_name(collection), validate_name(id))
        return self.__adapter.put(
            self.namespace,
            validate_name(collection),
            validate_name(id),
            data,
            if_version,
        )

    def get(self, collection: str, id: str) -> Document:
        self.__document("Get", validate_name(collection), validate_name(id))
        return self.__adapter.get(
            self.namespace, validate_name(collection), validate_name(id)
        )

    def find_one(self, collection: str, where: Iterable[Predicate]) -> Document | None:
        page = self.find(collection, where=where, limit=1)
        return page.items[0] if page.items else None

    def exists(self, collection: str, id: str) -> bool:
        try:
            self.get(collection, id)
            return True
        except DocumentNotFound:
            return False

    def delete(
        self, collection: str, id: str, *, if_version: int | None = None
    ) -> None:
        validate_version(if_version)
        self.__document("Delete", validate_name(collection), validate_name(id))
        self.__adapter.delete(
            self.namespace, validate_name(collection), validate_name(id), if_version
        )

    def find(
        self,
        collection: str,
        *,
        where: Iterable[Predicate] = (),
        order_by: OrderBy = None,
        limit: int = 100,
        cursor: str | None = None,
        max_bytes: int | None = None,
    ) -> Page:
        """A page of at most ``limit`` items, cut earlier by ``max_bytes``
        (see ``IDocumentAdapter.find``); follow ``cursor`` until it is None."""
        where = validate_query(where, order_by, limit)
        validate_max_bytes(max_bytes)
        # Checked once, on the collection: results are not filtered (RFC §5.5).
        self.__collection("Find", validate_name(collection))
        return self.__adapter.find(
            self.namespace,
            validate_name(collection),
            where,
            order_by,
            limit,
            cursor,
            **_max_bytes(self.__adapter.find, max_bytes),
        )

    def iterate(
        self,
        collection: str,
        *,
        where: Iterable[Predicate] = (),
        order_by: OrderBy = None,
        batch: int = 500,
        max_bytes: int | None = None,
    ) -> Iterator[Document]:
        # where/collection are validated once here rather than by find() on
        # every page, since neither changes across pages of the same query.
        where = validate_query(where, order_by, batch)
        validate_max_bytes(max_bytes)
        collection = validate_name(collection)
        self.__collection("Find", collection)
        cursor = None
        while True:
            page = self.__adapter.find(
                self.namespace,
                collection,
                where,
                order_by,
                batch,
                cursor,
                **_max_bytes(self.__adapter.find, max_bytes),
            )
            yield from page.items
            cursor = page.cursor
            if cursor is None:
                break

    def count(self, collection: str, where: Iterable[Predicate] = ()) -> int:
        where = validate_query(where)
        self.__collection("Count", validate_name(collection))
        return self.__adapter.count(self.namespace, validate_name(collection), where)

    def put_many(
        self, collection: str, items: Mapping[str, dict[str, Value]]
    ) -> list[Document]:
        return [self.put(collection, id, data) for id, data in items.items()]

    def delete_many(self, collection: str, where: Iterable[Predicate]) -> int:
        deleted = 0
        for document in self.iterate(collection, where=where):
            self.delete(collection, document.id, if_version=document.version)
            deleted += 1
        return deleted
