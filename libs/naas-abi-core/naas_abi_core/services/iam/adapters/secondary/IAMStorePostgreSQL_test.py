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


@pytest.mark.integration
def test_a_version_1_store_upgrades(schema):
    from naas_abi_core.services.iam.tests.iam_store_upgrade import check_upgrade
    from sqlalchemy import create_engine, text

    dsn, name = schema

    def execute(statement: str) -> None:
        engine = create_engine(sqlalchemy_url(dsn))
        with engine.begin() as conn:
            conn.execute(text(statement.format(schema=f'"{name}".')))
        engine.dispose()

    check_upgrade(lambda: IAMStorePostgreSQL(dsn, name), execute)


@pytest.mark.integration
def test_a_version_2_store_upgrades(schema):
    from naas_abi_core.services.iam.tests.iam_store_upgrade import (
        check_upgrade_from_2,
    )
    from sqlalchemy import create_engine, text

    dsn, name = schema

    def execute(statement: str) -> None:
        engine = create_engine(sqlalchemy_url(dsn))
        with engine.begin() as conn:
            conn.execute(text(statement.format(schema=f'"{name}".')))
        engine.dispose()

    check_upgrade_from_2(lambda: IAMStorePostgreSQL(dsn, name), execute)


@pytest.mark.integration
def test_two_processes_upgrade_a_version_1_store_together(schema):
    """The engine and the API open a version 1 store at once: the second waits
    for the first's ALTER TABLE, then finds the column there."""
    import threading
    import time

    from naas_abi_core.services.iam.adapters.secondary.iam_sql import SCHEMA_VERSION
    from naas_abi_core.services.iam.tests.iam_store_upgrade import DOWNGRADE
    from sqlalchemy import create_engine, text

    dsn, name = schema
    IAMStorePostgreSQL(dsn, name).close()
    engine = create_engine(sqlalchemy_url(dsn))
    with engine.begin() as conn:
        for statement in DOWNGRADE:
            conn.execute(text(statement.format(schema=f'"{name}".')))
    failures: list[BaseException] = []

    def second() -> None:
        try:
            IAMStorePostgreSQL(dsn, name).close()
        except BaseException as exc:  # noqa: BLE001 - reported below
            failures.append(exc)

    first = engine.connect()
    transaction = first.begin()
    for table in ("iam_principals", "iam_policies"):
        first.execute(
            text(
                f'ALTER TABLE "{name}".{table} ADD COLUMN owner_scope TEXT NOT NULL '
                "DEFAULT 'abi:-:-'"
            )
        )
    other = threading.Thread(target=second)
    other.start()
    with engine.connect() as watch:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            waiting = watch.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE wait_event_type = 'Lock' AND datname = current_database()"
                )
            ).scalar()
            if waiting:
                break
            time.sleep(0.05)
        assert waiting, "the second process never waited for the first"
    transaction.commit()
    first.close()
    other.join(timeout=30)
    assert not other.is_alive()
    assert failures == []
    with engine.connect() as conn:
        version = conn.execute(
            text(f'SELECT schema_version FROM "{name}".iam_state')
        ).scalar()
    engine.dispose()
    assert version == SCHEMA_VERSION


def test_dsn_and_schema_are_checked():
    assert sqlalchemy_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert sqlalchemy_url("postgres://h/db") == "postgresql+psycopg://h/db"
    with pytest.raises(ValueError):
        sqlalchemy_url("mysql://h/db")
    with pytest.raises(ValueError):
        IAMStorePostgreSQL("postgresql://h/db", 'bad"; DROP')
