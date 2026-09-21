from naas_abi_core.services.document.DocumentPort import IDocumentAdapter
from naas_abi_core.services.document.DocumentService import DocumentService


class DocumentFactory:
    @staticmethod
    def DocumentAdapterSQLite(
        path: str,
        *,
        timeout: float = 5.0,
    ) -> IDocumentAdapter:
        from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
            DocumentSecondaryAdapterSQLite,
        )

        return DocumentSecondaryAdapterSQLite(path, timeout=timeout)

    @staticmethod
    def DocumentServiceSQLite(
        path: str,
        namespace: str,
        *,
        timeout: float = 5.0,
    ) -> DocumentService:
        return DocumentService(
            DocumentFactory.DocumentAdapterSQLite(path, timeout=timeout), namespace
        )

    @staticmethod
    def DocumentAdapterPostgreSQL(
        dsn: str,
        *,
        schema: str = "abi_document",
        connect_timeout: int = 5,
        statement_timeout: int = 30000,
        pool_max_size: int = 10,
        pool_timeout: float = 5.0,
    ) -> IDocumentAdapter:
        from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterPostgreSQL import (
            DocumentSecondaryAdapterPostgreSQL,
        )

        return DocumentSecondaryAdapterPostgreSQL(
            dsn,
            schema=schema,
            connect_timeout=connect_timeout,
            statement_timeout=statement_timeout,
            pool_max_size=pool_max_size,
            pool_timeout=pool_timeout,
        )

    @staticmethod
    def DocumentServicePostgreSQL(
        dsn: str,
        namespace: str,
        *,
        schema: str = "abi_document",
        connect_timeout: int = 5,
        statement_timeout: int = 30000,
        pool_max_size: int = 10,
        pool_timeout: float = 5.0,
    ) -> DocumentService:
        return DocumentService(
            DocumentFactory.DocumentAdapterPostgreSQL(
                dsn,
                schema=schema,
                connect_timeout=connect_timeout,
                statement_timeout=statement_timeout,
                pool_max_size=pool_max_size,
                pool_timeout=pool_timeout,
            ),
            namespace,
        )
