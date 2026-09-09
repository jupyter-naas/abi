from naas_abi_core.services.document.DocumentService import DocumentService


class DocumentFactory:
    @staticmethod
    def DocumentServiceSQLite(
        path: str = "storage/documents.sqlite",
        namespace: str = "default",
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
        namespace: str = "default",
        *,
        schema: str = "abi_document",
        connect_timeout: int = 5,
        statement_timeout: int = 30000,
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
            ),
            namespace,
        )
