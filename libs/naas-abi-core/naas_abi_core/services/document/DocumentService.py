from collections.abc import Iterator, Mapping, Sequence

from naas_abi_core.services.document.DocumentPort import (
    CollectionSpec,
    Document,
    DocumentNotFound,
    IDocumentAdapter,
    OrderBy,
    Page,
    Predicate,
    Value,
    validate_data,
    validate_name,
    validate_query,
    validate_version,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class DocumentService(ServiceBase):
    """Namespace-bound collections. One document is the unit of atomicity.

    put replaces the complete document. if_version=None is unconditional,
    zero is create-only, and a positive version is compare-and-swap. Bulk
    helpers can commit a prefix before an error; they are not transactions.
    """

    def __init__(self, adapter: IDocumentAdapter, namespace: str):
        super().__init__()
        self.__adapter = adapter
        self.__namespace = validate_name(namespace)

    @property
    def namespace(self) -> str:
        return self.__namespace

    def _for_namespace(self, namespace: str) -> "DocumentService":
        """Composition-root hook; module proxies choose the namespace."""
        return DocumentService(self.__adapter, namespace)

    def ensure_collection(self, spec: CollectionSpec) -> None:
        self.__adapter.ensure_collection(self.__namespace, spec)

    def drop_collection(self, collection: str) -> None:
        self.__adapter.drop_collection(self.__namespace, validate_name(collection))

    def collections(self) -> list[str]:
        return self.__adapter.collections(self.__namespace)

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
        return self.__adapter.put(
            self.__namespace,
            validate_name(collection),
            validate_name(id),
            data,
            if_version,
        )

    def get(self, collection: str, id: str) -> Document:
        return self.__adapter.get(
            self.__namespace, validate_name(collection), validate_name(id)
        )

    def find_one(self, collection: str, where: Sequence[Predicate]) -> Document | None:
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
        self.__adapter.delete(
            self.__namespace, validate_name(collection), validate_name(id), if_version
        )

    def find(
        self,
        collection: str,
        *,
        where: Sequence[Predicate] = (),
        order_by: OrderBy = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> Page:
        validate_query(where, order_by, limit)
        return self.__adapter.find(
            self.__namespace, validate_name(collection), where, order_by, limit, cursor
        )

    def iterate(
        self,
        collection: str,
        *,
        where: Sequence[Predicate] = (),
        order_by: OrderBy = None,
        batch: int = 500,
    ) -> Iterator[Document]:
        cursor = None
        while True:
            page = self.find(
                collection, where=where, order_by=order_by, limit=batch, cursor=cursor
            )
            yield from page.items
            cursor = page.cursor
            if cursor is None:
                break

    def count(self, collection: str, where: Sequence[Predicate] = ()) -> int:
        validate_query(where)
        return self.__adapter.count(self.__namespace, validate_name(collection), where)

    def put_many(
        self, collection: str, items: Mapping[str, dict[str, Value]]
    ) -> list[Document]:
        return [self.put(collection, id, data) for id, data in items.items()]

    def delete_many(self, collection: str, where: Sequence[Predicate]) -> int:
        deleted = 0
        for document in self.iterate(collection, where=where):
            self.delete(collection, document.id, if_version=document.version)
            deleted += 1
        return deleted
