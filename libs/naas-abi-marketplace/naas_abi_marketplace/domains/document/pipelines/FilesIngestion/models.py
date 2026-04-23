from sqlmodel import SQLModel, Field


class File(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    hash: str

    @staticmethod
    def engine():
        from naas_abi_marketplace.domains.document.lib.sqlmodel_sqlite import (
            create_sqlite_engine,
        )

        sqlite_engine = create_sqlite_engine("files.db")

        File.metadata.create_all(sqlite_engine)

        return sqlite_engine
