from naas_abi_core.services.document.DocumentService import DocumentService


class DocumentFactory:
    @staticmethod
    def DocumentServiceSQLite(
        path: str,
        namespace: str,
        *,
        timeout: float = 5.0,
    ) -> DocumentService:
        from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
            DocumentSecondaryAdapterSQLite,
        )

        return DocumentService(
            DocumentSecondaryAdapterSQLite(path, timeout=timeout), namespace
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
        from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterPostgreSQL import (
            DocumentSecondaryAdapterPostgreSQL,
        )

        return DocumentService(
            DocumentSecondaryAdapterPostgreSQL(
                dsn,
                schema=schema,
                connect_timeout=connect_timeout,
                statement_timeout=statement_timeout,
                pool_max_size=pool_max_size,
                pool_timeout=pool_timeout,
            ),
            namespace,
        )
