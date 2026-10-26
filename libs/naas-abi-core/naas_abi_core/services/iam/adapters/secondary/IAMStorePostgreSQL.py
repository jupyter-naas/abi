"""PostgreSQL ``IAMStore``: the Docker templates and production.

The tables live in their own schema (``abi_iam`` by default) of an existing
database, created at boot when missing. Render the DSN from the secret service
(``IAM_POSTGRES_DSN``); it is never logged.
"""

from __future__ import annotations

import re

from naas_abi_core.services.iam.adapters.secondary.iam_sql import IAMStoreSQL
from sqlalchemy import create_engine, text

_SCHEMA = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def sqlalchemy_url(dsn: str) -> str:
    """A libpq DSN as a SQLAlchemy URL on psycopg 3."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if dsn.startswith(prefix):
            return "postgresql+psycopg://" + dsn[len(prefix) :]
    raise ValueError("The IAM PostgreSQL DSN must start with postgresql://")


class IAMStorePostgreSQL(IAMStoreSQL):
    def __init__(
        self,
        dsn: str,
        schema: str = "abi_iam",
        *,
        connect_timeout: int = 5,
        statement_timeout_ms: int = 30000,
        pool_size: int = 5,
    ) -> None:
        if not _SCHEMA.match(schema):
            raise ValueError(f"Invalid PostgreSQL schema name {schema!r}")
        engine = create_engine(
            sqlalchemy_url(dsn),
            pool_size=pool_size,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": connect_timeout,
                "options": f"-c statement_timeout={int(statement_timeout_ms)}",
            },
        )
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        super().__init__(
            engine.execution_options(schema_translate_map={None: schema}), schema=schema
        )
        self.schema = schema
