import pytest
# Short term memory

# Long term memory
from langgraph.store.postgres import PostgresStore

DB_URI = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"

@pytest.fixture
def long_term_memory():
    from psycopg import Connection
    from psycopg.rows import dict_row

    conn = Connection.connect(DB_URI, autocommit=True, prepare_threshold=0, row_factory=dict_row)
    return PostgresStore(conn)


def test_long_term_memory(long_term_memory):

    long_term_memory.put(("tests",), "123", {
        "test": "is working"
    })
    
    assert long_term_memory.get(("tests",), "123").value == {
        "test": "is working"
    }


