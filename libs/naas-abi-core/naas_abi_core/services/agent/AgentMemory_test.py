"""Long-term memory on PostgreSQL (langgraph's PostgresStore).

Needs a reachable PostgreSQL: ``AGENT_TEST_POSTGRES_DSN``, or the local
default below. Skipped when none answers.
"""

import os

import pytest

DB_URI = os.environ.get(
    "AGENT_TEST_POSTGRES_DSN", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
)


@pytest.fixture
def long_term_memory():
    import psycopg
    from langgraph.store.postgres import PostgresStore
    from psycopg.rows import dict_row

    try:
        conn = psycopg.Connection.connect(
            DB_URI,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
            connect_timeout=3,
        )
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL is not reachable at the test DSN: {exc}")
    store = PostgresStore(conn)
    store.setup()
    yield store
    conn.close()


def test_long_term_memory(long_term_memory):
    long_term_memory.put(("tests",), "123", {"test": "is working"})

    assert long_term_memory.get(("tests",), "123").value == {"test": "is working"}
