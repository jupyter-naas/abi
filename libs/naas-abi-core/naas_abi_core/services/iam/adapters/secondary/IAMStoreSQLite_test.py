import threading

import pytest
from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import IAMStoreSQLite
from naas_abi_core.services.iam.IAMPorts import new_id
from naas_abi_core.services.iam.tests.iam__secondary_adapter__generic_test import (
    IAMStoreContract,
    user,
)


class TestIAMStoreSQLite(IAMStoreContract):
    @pytest.fixture
    def store(self, tmp_path):
        store = IAMStoreSQLite(str(tmp_path / "iam" / "iam.sqlite"))
        yield store
        store.close()


def test_in_memory_database(tmp_path):
    store = IAMStoreSQLite(":memory:")
    bob = store.create_principal(user())
    assert store.get_principal(bob.id) == bob
    store.close()


def test_state_survives_reopening(tmp_path):
    path = str(tmp_path / "iam.sqlite")
    first = IAMStoreSQLite(path)
    bob = first.create_principal(user())
    install_id, revision = first.install_id(), first.revision()
    first.close()
    second = IAMStoreSQLite(path)
    assert second.get_principal(bob.id) == bob
    assert (second.install_id(), second.revision()) == (install_id, revision)
    second.close()


def test_concurrent_writers_queue_instead_of_failing(tmp_path):
    path = str(tmp_path / "iam.sqlite")
    stores = [IAMStoreSQLite(path) for _ in range(4)]
    errors: list[BaseException] = []

    def write(store):
        try:
            for i in range(10):
                store.create_principal(user(f"{id(store)}-{i}"))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(s,)) for s in stores]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(stores[0].list_principals(limit=100).items) == 40
    assert stores[0].revision() >= 40
    for store in stores:
        store.close()


def test_closed_store_refuses_use(tmp_path):
    store = IAMStoreSQLite(str(tmp_path / "iam.sqlite"))
    store.close()
    with pytest.raises(RuntimeError):
        store.get_principal(new_id("usr"))


def test_a_version_1_store_upgrades(tmp_path):
    import sqlite3

    from naas_abi_core.services.iam.tests.iam_store_upgrade import check_upgrade

    path = str(tmp_path / "iam.sqlite")

    def execute(statement: str) -> None:
        with sqlite3.connect(path) as conn:
            conn.execute(statement.format(schema=""))

    check_upgrade(lambda: IAMStoreSQLite(path), execute)


def test_a_version_2_store_upgrades(tmp_path):
    import sqlite3

    from naas_abi_core.services.iam.tests.iam_store_upgrade import (
        check_upgrade_from_2,
    )

    path = str(tmp_path / "iam.sqlite")

    def execute(statement: str) -> None:
        with sqlite3.connect(path) as conn:
            conn.execute(statement.format(schema=""))

    check_upgrade_from_2(lambda: IAMStoreSQLite(path), execute)


def test_a_version_3_store_upgrades(tmp_path):
    import sqlite3

    from naas_abi_core.services.iam.tests.iam_store_upgrade import (
        check_upgrade_from_3,
    )

    path = str(tmp_path / "iam.sqlite")

    def execute(statement: str) -> None:
        with sqlite3.connect(path) as conn:
            conn.execute(statement.format(schema=""))

    check_upgrade_from_3(lambda: IAMStoreSQLite(path), execute)


def test_a_version_4_store_upgrades(tmp_path):
    import sqlite3

    from naas_abi_core.services.iam.tests.iam_store_upgrade import (
        check_upgrade_from_4,
    )

    path = str(tmp_path / "iam.sqlite")

    def execute(statement: str) -> None:
        with sqlite3.connect(path) as conn:
            conn.execute(statement.format(schema=""))

    check_upgrade_from_4(lambda: IAMStoreSQLite(path), execute)


def test_a_catalog_stored_before_the_format_reads_as_format_one(tmp_path):
    """The previous version stored catalogs without ``format``: read back, their
    flags are unknown (``ActionCatalog.flags_known``); what this version stores
    carries it."""
    import json
    import sqlite3

    from naas_abi_core.services.iam.adapters.secondary.IAMStoreSQLite import (
        IAMStoreSQLite,
    )
    from naas_abi_core.services.iam.catalog import (
        CATALOG_FORMAT,
        ActionCatalog,
        ActionSpec,
        ResourceType,
    )

    path = str(tmp_path / "iam.sqlite")
    catalog = ActionCatalog(
        service="nexus",
        version=6,
        resource_types=(ResourceType("feature"),),
        actions=(ActionSpec("UseFeature", "read", ("feature",)),),
    )
    IAMStoreSQLite(path).put_catalog(catalog)
    assert IAMStoreSQLite(path).list_catalogs()[0].format == CATALOG_FORMAT
    old = json.dumps(catalog.to_dict(), sort_keys=True)  # no "format", as before
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE iam_catalogs SET document = ? WHERE service = 'nexus'", (old,)
        )
    (found,) = IAMStoreSQLite(path).list_catalogs()
    assert found.format == 1 and not found.flags_known
