"""LangGraph's PostgreSQL checkpoint tables in a throwaway schema, for tests.

Runs on the database the document tests use (``DOCUMENT_TEST_POSTGRES_DSN``);
without it, the tests that need it skip.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import make_conninfo


@contextmanager
def langgraph_postgres() -> Iterator[str]:
    """A connection string whose search path is a new schema holding LangGraph's
    tables (``PostgresSaver.setup``); the schema is dropped afterwards."""
    dsn = os.environ.get("DOCUMENT_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set DOCUMENT_TEST_POSTGRES_DSN to run on PostgreSQL")
    schema = "langgraph_test_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(f'CREATE SCHEMA "{schema}"')
    try:
        url = make_conninfo(dsn, options=f"-c search_path={schema}")
        with PostgresSaver.from_conn_string(url) as saver:
            saver.setup()
        yield url
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
