"""Runs on PostgreSQL when IAM_TEST_POSTGRES_DSN (or the document tests'
DOCUMENT_TEST_POSTGRES_DSN) names a database; skipped otherwise. ``schema``
(a fresh schema, dropped after) is the IAM tests' fixture (``conftest.py``)."""

import pytest
from naas_abi_core.services.iam.adapters.secondary.IAMStorePostgreSQL import (
    IAMStorePostgreSQL,
    sqlalchemy_url,
)
from naas_abi_core.services.iam.tests.iam__secondary_adapter__generic_test import (
    IAMStoreContract,
    run_a_container_registered_meanwhile_by_another_process,
    user,
)


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
def test_a_version_3_store_upgrades(schema):
    from naas_abi_core.services.iam.tests.iam_store_upgrade import (
        check_upgrade_from_3,
    )
    from sqlalchemy import create_engine, text

    dsn, name = schema

    def execute(statement: str) -> None:
        engine = create_engine(sqlalchemy_url(dsn))
        with engine.begin() as conn:
            conn.execute(text(statement.format(schema=f'"{name}".')))
        engine.dispose()

    check_upgrade_from_3(lambda: IAMStorePostgreSQL(dsn, name), execute)


@pytest.mark.integration
def test_a_version_4_store_upgrades(schema):
    from naas_abi_core.services.iam.tests.iam_store_upgrade import (
        check_upgrade_from_4,
    )
    from sqlalchemy import create_engine, text

    dsn, name = schema

    def execute(statement: str) -> None:
        engine = create_engine(sqlalchemy_url(dsn))
        with engine.begin() as conn:
            conn.execute(text(statement.format(schema=f'"{name}".')))
        engine.dispose()

    check_upgrade_from_4(lambda: IAMStorePostgreSQL(dsn, name), execute)


@pytest.mark.integration
def test_a_version_5_store_upgrades(schema):
    from naas_abi_core.services.iam.tests.iam_store_upgrade import (
        check_upgrade_from_5,
    )
    from sqlalchemy import create_engine, text

    dsn, name = schema

    def execute(statement: str) -> None:
        engine = create_engine(sqlalchemy_url(dsn))
        with engine.begin() as conn:
            conn.execute(text(statement.format(schema=f'"{name}".')))
        engine.dispose()

    check_upgrade_from_5(lambda: IAMStorePostgreSQL(dsn, name), execute)


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
                "DEFAULT 'abi:'"
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


@pytest.mark.integration
def test_writes_wait_for_each_other_on_the_state_row(schema):
    """Every write locks the state row before it checks anything, so a delete of
    a parent and a re-parent under it never both commit: the second one runs
    after the first and sees what it wrote."""
    import threading
    import time
    from dataclasses import replace

    from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError
    from naas_abi_core.services.iam.tests.iam__secondary_adapter__generic_test import (
        policy,
    )
    from sqlalchemy import create_engine, text

    dsn, name = schema
    store = IAMStorePostgreSQL(dsn, name)
    parent = store.create_policy(policy())
    child = store.create_policy(policy())
    engine = create_engine(sqlalchemy_url(dsn))
    first = engine.connect()
    transaction = first.begin()
    # Another writer holds the state row: the delete below waits for it.
    first.execute(text(f'SELECT id FROM "{name}".iam_state FOR UPDATE'))
    failures: list[BaseException] = []

    def delete() -> None:
        try:
            store.delete_policy(parent.id)
        except BaseException as exc:  # noqa: BLE001 - reported below
            failures.append(exc)

    other = threading.Thread(target=delete)
    other.start()
    time.sleep(0.5)
    assert other.is_alive(), "the delete did not wait for the state row"
    transaction.commit()
    first.close()
    other.join(timeout=30)
    assert failures == []
    # Deleted first: re-parenting under it now finds no parent.
    with pytest.raises(IAMNotFoundError):
        store.update_policy(replace(child, parent_id=parent.id), 1)
    store.close()
    engine.dispose()


@pytest.mark.integration
def test_a_container_registered_meanwhile_by_another_process(schema):
    dsn, name = schema
    store, other = IAMStorePostgreSQL(dsn, name), IAMStorePostgreSQL(dsn, name)
    try:
        run_a_container_registered_meanwhile_by_another_process(store, other)
    finally:
        store.close()
        other.close()
