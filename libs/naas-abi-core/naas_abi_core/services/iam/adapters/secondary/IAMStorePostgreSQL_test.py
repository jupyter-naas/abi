"""Runs on PostgreSQL when IAM_TEST_POSTGRES_DSN (or the document tests'
DOCUMENT_TEST_POSTGRES_DSN) names a database; skipped otherwise."""

import os
from uuid import uuid4

import pytest
from naas_abi_core.services.iam.adapters.secondary.IAMStorePostgreSQL import (
    IAMStorePostgreSQL,
    sqlalchemy_url,
)
from naas_abi_core.services.iam.tests.iam__secondary_adapter__generic_test import (
    IAMStoreContract,
    user,
)


def _dsn() -> str:
    dsn = os.environ.get("IAM_TEST_POSTGRES_DSN") or os.environ.get(
        "DOCUMENT_TEST_POSTGRES_DSN"
    )
    if not dsn:
        pytest.skip("Set IAM_TEST_POSTGRES_DSN to run on PostgreSQL")
    return dsn


@pytest.fixture
def schema():
    dsn = _dsn()
    name = f"iam_test_{uuid4().hex[:12]}"
    yield dsn, name
    from sqlalchemy import create_engine, text

    engine = create_engine(sqlalchemy_url(dsn))
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{name}" CASCADE'))
    engine.dispose()


@pytest.mark.integration
class TestIAMStorePostgreSQL(IAMStoreContract):
    @pytest.fixture
    def store(self, schema):
        dsn, name = schema
        store = IAMStorePostgreSQL(dsn, name)
        yield store
        store.close()


@pytest.mark.integration
def test_tables_live_in_their_schema(schema):
    dsn, name = schema
    store = IAMStorePostgreSQL(dsn, name)
    bob = store.create_principal(user())
    store.close()
    from sqlalchemy import create_engine, text

    engine = create_engine(sqlalchemy_url(dsn))
    with engine.connect() as conn:
        found = conn.execute(
            text(f'SELECT count(*) FROM "{name}".iam_principals WHERE id = :id'),
            {"id": bob.id},
        ).scalar()
    engine.dispose()
    assert found == 1


def test_dsn_and_schema_are_checked():
    assert sqlalchemy_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert sqlalchemy_url("postgres://h/db") == "postgresql+psycopg://h/db"
    with pytest.raises(ValueError):
        sqlalchemy_url("mysql://h/db")
    with pytest.raises(ValueError):
        IAMStorePostgreSQL("postgresql://h/db", 'bad"; DROP')
