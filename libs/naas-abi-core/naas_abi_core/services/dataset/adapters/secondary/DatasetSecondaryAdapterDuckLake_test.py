import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from naas_abi_core.services.dataset.adapters.secondary import (
    DatasetSecondaryAdapterDuckLake as ducklake_module,
)
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
    CATALOG_ALIAS,
    DatasetSecondaryAdapterDuckLake,
    _S3Settings,
)
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetNotFoundError,
    DatasetSchemaError,
    DatasetSpec,
    PartitionSpec,
)
from naas_abi_core.services.dataset.tests.dataset__secondary_adapter__generic_test import (
    DatasetSecondaryAdapterContract,
)


class TestDatasetSecondaryAdapterDuckLake(DatasetSecondaryAdapterContract):
    @pytest.fixture
    def adapter(self, tmp_path):
        return DatasetSecondaryAdapterDuckLake(
            catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
            data_path=str(tmp_path / "datasets"),
            max_retries=10,
            retry_base_delay_seconds=0.01,
        )

    def test_write_stream_retries_replay_staged_rows_not_the_iterator(
        self, adapter, monkeypatch
    ):
        import duckdb

        adapter.create(self._spec())
        current_snapshot = adapter._current_snapshot
        conflicts = []

        def conflict_once(con):
            if not conflicts:
                conflicts.append(1)
                raise duckdb.TransactionException("transaction conflict")
            return current_snapshot(con)

        monkeypatch.setattr(adapter, "_current_snapshot", conflict_once)

        adapter.write_stream("github_commits", self._commits(500), namespace="acme")

        assert conflicts == [1]  # the transaction ran twice
        assert self._totals(adapter) == (500, sum(range(500)))

    def test_reserved_column_names_are_quoted(self, adapter):
        spec = DatasetSpec(
            name="time_entries",
            namespace="clockify",
            columns=(
                ColumnSpec(name="id", type="string"),
                ColumnSpec(name="start", type="timestamp"),
                ColumnSpec(name="end", type="timestamp"),
                ColumnSpec(name="duration_hours", type="double"),
            ),
            partitions=(PartitionSpec(column="start", transform="month"),),
            primary_key=("id",),
        )
        adapter.create(spec)
        adapter.write(
            "time_entries",
            [
                {
                    "id": "te-1",
                    "start": "2026-04-15T09:00:00Z",
                    "end": "2026-04-15T12:00:00Z",
                    "duration_hours": 3.0,
                }
            ],
            namespace="clockify",
        )
        total = adapter.query(
            "SELECT SUM(duration_hours) AS hours FROM time_entries",
            namespace="clockify",
        )
        assert total.rows[0]["hours"] == 3.0
        row = adapter.query(
            'SELECT "end" AS ended_at FROM time_entries',
            namespace="clockify",
        )
        assert row.rows[0]["ended_at"] is not None

    def test_upsert_requires_primary_key(self, adapter):
        adapter.create(
            DatasetSpec(
                name="unkeyed",
                columns=(ColumnSpec(name="value", type="string"),),
            )
        )
        with pytest.raises(DatasetSchemaError, match="has no primary key"):
            adapter.write("unkeyed", [{"value": "x"}], mode="upsert")

    def test_delete_preserves_historical_rows(self, adapter):
        adapter.create(
            DatasetSpec(
                name="events",
                columns=(
                    ColumnSpec(name="id", type="integer"),
                    ColumnSpec(name="value", type="string"),
                ),
                primary_key=("id",),
            )
        )
        before_delete = adapter.write("events", [{"id": 1, "value": "keep in history"}])

        adapter.query("DELETE FROM events WHERE id = 1")

        assert adapter.query("SELECT * FROM events").rows == []
        assert adapter.query(
            "SELECT * FROM events", snapshot_id=before_delete.snapshot_id
        ).rows == [{"id": 1, "value": "keep in history"}]

    def test_concurrent_sqlite_writers_preserve_acknowledged_appends(self, adapter):
        adapter.create(
            DatasetSpec(
                name="events",
                columns=(
                    ColumnSpec(name="id", type="integer"),
                    ColumnSpec(name="value", type="string"),
                ),
                primary_key=("id",),
            )
        )

        def append(index: int) -> None:
            adapter.write("events", [{"id": index, "value": f"event-{index}"}])

        with ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(append, range(3)))

        result = adapter.query("SELECT id FROM events ORDER BY id")
        assert [row["id"] for row in result.rows] == list(range(3))

    def test_retriable_attach_conflict_replays_against_fresh_connection(
        self, adapter, monkeypatch
    ):
        import duckdb

        adapter.create(
            DatasetSpec(
                name="events",
                columns=(ColumnSpec(name="id", type="integer"),),
            )
        )
        real_connect = adapter._connect
        attempts = 0

        def flaky_connect(*, snapshot_id=None):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise duckdb.TransactionException("simulated catalog conflict")
            return real_connect(snapshot_id=snapshot_id)

        monkeypatch.setattr(adapter, "_connect", flaky_connect)
        adapter.write("events", [{"id": 1}])

        assert attempts == 3
        assert adapter.query("SELECT * FROM events").rows == [{"id": 1}]

    def test_write_returns_the_snapshot_committed_by_its_connection(
        self, adapter, monkeypatch
    ):
        adapter.create(
            DatasetSpec(
                name="events",
                columns=(ColumnSpec(name="id", type="integer"),),
            )
        )
        monkeypatch.setattr(adapter, "_current_snapshot", lambda con: 999_999)

        written = adapter.write("events", [{"id": 1}])

        assert written.snapshot_id != 999_999
        assert written.snapshot_id == adapter.list_snapshots()[-1].snapshot_id

    def test_noop_write_returns_the_current_snapshot(self, adapter):
        created = adapter.create(
            DatasetSpec(
                name="events",
                columns=(ColumnSpec(name="id", type="integer"),),
            )
        )

        written = adapter.write("events", [])

        assert written.snapshot_id == created.snapshot_id

    def test_describe_reads_one_table_from_the_metadata_catalog(
        self, adapter, monkeypatch
    ):
        """duckdb_tables() lists every table in the lake: seconds at a few hundred."""
        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        statements: list[str] = []
        real_read = adapter._read

        class Recording:
            def __init__(self, con):
                self._con = con

            def execute(self, sql, *args):
                statements.append(sql)
                return self._con.execute(sql, *args)

        monkeypatch.setattr(
            adapter,
            "_read",
            lambda operation: real_read(lambda con: operation(Recording(con))),
        )

        assert adapter.describe("events").name == "events"
        assert not any("duckdb_tables" in sql for sql in statements)

    def test_describe_sees_a_recreated_table_not_the_dropped_one(self, adapter):
        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        adapter.drop("events")
        with pytest.raises(DatasetNotFoundError):
            adapter.describe("events")

        adapter.create(
            DatasetSpec(
                name="events", columns=(ColumnSpec(name="label", type="string"),)
            )
        )

        assert [c.name for c in adapter.describe("events").columns] == ["label"]

    def test_reads_reuse_a_single_connection_across_calls(self, adapter, monkeypatch):
        import duckdb

        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        adapter.write("events", [{"id": 1}])

        real_connect = duckdb.connect
        connect_calls = []

        def counting_connect(*args, **kwargs):
            connect_calls.append((args, kwargs))
            return real_connect(*args, **kwargs)

        monkeypatch.setattr(duckdb, "connect", counting_connect)

        adapter.describe("events")
        adapter.list()
        adapter.query("SELECT * FROM events")
        adapter.list_snapshots()
        adapter._snapshot_exists(1)

        assert len(connect_calls) == 1

    def test_reused_read_connection_sees_writes_from_other_connections(self, tmp_path):
        catalog = f"sqlite:{tmp_path / 'datasets.sqlite'}"
        data_path = str(tmp_path / "datasets")
        reader = DatasetSecondaryAdapterDuckLake(catalog=catalog, data_path=data_path)
        writer = DatasetSecondaryAdapterDuckLake(catalog=catalog, data_path=data_path)

        reader.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        # Warm the reader's cached connection before the other adapter writes.
        assert reader.list() != []

        writer.write("events", [{"id": 1}])

        assert reader.query("SELECT id FROM events").rows == [{"id": 1}]

    def test_a_failed_read_does_not_break_the_shared_connection(self, adapter):
        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        adapter.write("events", [{"id": 1}])

        with pytest.raises(Exception):
            adapter.query("SELECT * FROM not_a_real_table")

        assert adapter.query("SELECT id FROM events").rows == [{"id": 1}]

    def test_concurrent_reads_share_one_connection(self, adapter):
        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        adapter.write("events", [{"id": i} for i in range(20)])

        def read(_: int) -> int:
            return adapter.query("SELECT count(*) AS n FROM events").rows[0]["n"]

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(read, range(40)))

        assert results == [20] * 40

    def test_pinned_snapshot_query_still_uses_its_own_connection(
        self, adapter, monkeypatch
    ):
        """SNAPSHOT_VERSION is fixed at ATTACH time, so time travel can't share
        the adapter's one cached, latest-snapshot read connection."""
        import duckdb

        created = adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        adapter.write("events", [{"id": 1}])
        # Warm the shared read connection at the latest snapshot.
        adapter.list()

        real_connect = duckdb.connect
        connect_calls = []

        def counting_connect(*args, **kwargs):
            connect_calls.append((args, kwargs))
            return real_connect(*args, **kwargs)

        monkeypatch.setattr(duckdb, "connect", counting_connect)

        result = adapter.query("SELECT * FROM events", snapshot_id=created.snapshot_id)

        assert result.rows == []
        assert len(connect_calls) == 1

    def test_pinned_reads_reuse_connection_and_keep_snapshots_isolated(
        self, adapter, monkeypatch
    ):
        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        first = adapter.write("events", [{"id": 1}]).snapshot_id
        second = adapter.write("events", [{"id": 2}]).snapshot_id
        connect = adapter._connect
        snapshots = []

        def counted(**kwargs):
            snapshots.append(kwargs.get("snapshot_id"))
            return connect(**kwargs)

        adapter.list()
        monkeypatch.setattr(adapter, "_connect", counted)

        def read(snapshot):
            return adapter.query(
                "SELECT id FROM events ORDER BY id", snapshot_id=snapshot
            ).rows

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(read, [first, second] * 8))
        assert results == [[{"id": 1}], [{"id": 1}, {"id": 2}]] * 8
        assert sorted(snapshots) == sorted([first, second])
        with pytest.raises(Exception):
            adapter.query("SELECT * FROM absent", snapshot_id=first)
        assert read(first) == [{"id": 1}]

    def test_snapshot_connection_cache_is_bounded(self, adapter):
        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        versions = [adapter.write("events", [{"id": n}]).snapshot_id for n in range(6)]
        for version in versions:
            adapter.query("SELECT count(*) FROM events", snapshot_id=version)
        assert len(adapter._snapshot_connections) <= 4
        assert adapter.query("SELECT id FROM events", snapshot_id=versions[0]).rows == [
            {"id": 0}
        ]

    def test_retiring_snapshot_cache_does_not_interrupt_active_cursor(self, adapter):
        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        snapshot = adapter.write("events", [{"id": 1}]).snapshot_id
        cursor = adapter._get_snapshot_connection(snapshot).cursor()
        try:
            adapter.flush("events")
            assert not adapter._snapshot_connections
            assert cursor.execute(
                "SELECT id FROM abi_datasets.default.events"
            ).fetchall() == [(1,)]
        finally:
            cursor.close()
        assert adapter.query("SELECT id FROM events", snapshot_id=snapshot).rows == [
            {"id": 1}
        ]

    def test_connect_owns_ducklake_catalog_migrations(self, adapter, monkeypatch):
        import duckdb

        class RecordingConnection:
            def __init__(self):
                self.statements = []

            def execute(self, statement):
                self.statements.append(statement)
                return self

            def close(self):
                return None

        connection = RecordingConnection()
        monkeypatch.setattr(duckdb, "connect", lambda: connection)

        assert adapter._connect() is connection
        attach = next(
            statement
            for statement in connection.statements
            if statement.startswith("ATTACH ")
        )
        assert "AUTOMATIC_MIGRATION" in attach


def test_dataset_spec_validates_primary_key_and_partition_columns():
    with pytest.raises(ValueError, match="Primary key columns"):
        DatasetSpec(
            name="events",
            columns=(ColumnSpec(name="id", type="string"),),
            primary_key=("missing",),
        )
    with pytest.raises(ValueError, match="Partition columns"):
        DatasetSpec(
            name="events",
            columns=(ColumnSpec(name="id", type="string"),),
            partitions=(PartitionSpec(column="missing"),),
        )


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("ABI_TEST_DUCKLAKE_POSTGRES") != "1",
    reason="set ABI_TEST_DUCKLAKE_POSTGRES=1 to run the PostgreSQL catalog test",
)
def test_postgres_catalog_concurrent_writers_preserve_acknowledged_appends(tmp_path):
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        "postgres:16-alpine",
        username="ducklake",
        password="ducklake",
        dbname="ducklake",
    ) as postgres:
        catalog = f"postgres:{postgres.get_connection_url(driver=None)}"
        data_path = str(tmp_path / "datasets")
        setup_adapter = DatasetSecondaryAdapterDuckLake(
            catalog=catalog,
            data_path=data_path,
        )
        setup_adapter.create(
            DatasetSpec(
                name="events",
                columns=(
                    ColumnSpec(name="id", type="integer"),
                    ColumnSpec(name="value", type="string"),
                ),
                primary_key=("id",),
            )
        )

        def append(index: int) -> None:
            adapter = DatasetSecondaryAdapterDuckLake(
                catalog=catalog,
                data_path=data_path,
                max_retries=20,
                retry_base_delay_seconds=0.01,
                retry_max_delay_seconds=0.2,
            )
            adapter.write("events", [{"id": index, "value": f"event-{index}"}])

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(append, range(8)))

        result = setup_adapter.query("SELECT id FROM events ORDER BY id")
        assert [row["id"] for row in result.rows] == list(range(8))


def _two_tables(adapter: DatasetSecondaryAdapterDuckLake) -> None:
    for name in ("slow", "busy"):
        adapter.create(
            DatasetSpec(
                name=name,
                columns=(ColumnSpec(name="id", type="integer"),),
                primary_key=("id",),
            )
        )


def _racing_write(
    catalog: str, data_path: str, *, commit_retries: int
) -> tuple[int, Exception | None]:
    """A write to ``slow`` while another writer commits to ``busy``: how many
    times the slow write's transaction ran, and what it raised."""
    slow = DatasetSecondaryAdapterDuckLake(
        catalog=catalog,
        data_path=data_path,
        max_retries=0,
        commit_retries=commit_retries,
    )
    busy = DatasetSecondaryAdapterDuckLake(catalog=catalog, data_path=data_path)
    runs = 0

    def operation(con):
        nonlocal runs
        runs += 1
        con.execute(
            "INSERT INTO abi_datasets.default.slow VALUES (?)",  # nosec B608
            [runs],
        )
        if runs == 1:  # another writer commits while this one is still open
            busy.write("busy", [{"id": 1}])

    try:
        slow._write_transaction(operation)
    except Exception as exc:  # noqa: BLE001 - returned for the assertion
        return runs, exc
    return runs, None


def test_commits_on_other_tables_no_longer_fail_a_running_write(tmp_path):
    adapter = DatasetSecondaryAdapterDuckLake(
        catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
        data_path=str(tmp_path / "datasets"),
        commit_retries=3,
    )
    con = adapter._connect()
    try:
        setting = con.execute(
            "SELECT current_setting('ducklake_max_retry_count')"
        ).fetchone()
    finally:
        con.close()
    assert int(setting[0]) == 3
    with pytest.raises(ValueError, match="commit_retries"):
        DatasetSecondaryAdapterDuckLake(
            catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
            data_path=str(tmp_path / "datasets"),
            commit_retries=-1,
        )


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("ABI_TEST_DUCKLAKE_POSTGRES") != "1",
    reason="set ABI_TEST_DUCKLAKE_POSTGRES=1 to run the PostgreSQL catalog test",
)
def test_postgres_catalog_write_survives_a_commit_to_another_table(tmp_path):
    """wise_list_transactions failed with INTERNAL on 2026-10-13: its 46 s write
    lost every commit race to a writer committing elsewhere once a second."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        "postgres:16-alpine",
        username="ducklake",
        password="ducklake",
        dbname="ducklake",
    ) as postgres:
        catalog = f"postgres:{postgres.get_connection_url(driver=None)}"
        data_path = str(tmp_path / "datasets")
        _two_tables(DatasetSecondaryAdapterDuckLake(catalog, data_path))

        # Without DuckLake's own commit retry, the unrelated commit fails it.
        runs, error = _racing_write(catalog, data_path, commit_retries=0)
        assert runs == 1
        assert error is not None and "retry count of 0" in str(error)

        # With it, only the commit is redone: the transaction ran once.
        runs, error = _racing_write(catalog, data_path, commit_retries=10)
        assert (runs, error) == (1, None)
        result = DatasetSecondaryAdapterDuckLake(catalog, data_path).query(
            "SELECT count(*) AS n FROM slow"
        )
        assert result.rows == [{"n": 1}]


class TestObjectStoreDataPath:
    """``data_path`` may use S3-compatible storage when explicitly configured."""

    @pytest.mark.parametrize(
        "data_path",
        (
            "gs://bucket/datasets/",
            "gcs://bucket/datasets/",
            "r2://bucket/datasets/",
            "azure://container/datasets/",
            "abfss://container/datasets/",
        ),
    )
    def test_unsupported_object_store_schemes_are_rejected(self, tmp_path, data_path):
        with pytest.raises(ValueError, match="Unsupported dataset data_path scheme"):
            DatasetSecondaryAdapterDuckLake(
                catalog=f"sqlite:{tmp_path / 'catalog.sqlite'}",
                data_path=data_path,
            )

    @pytest.mark.parametrize("scheme", ("s3", "s3a"))
    def test_s3_compatible_data_path_schemes_are_accepted(self, tmp_path, scheme):
        DatasetSecondaryAdapterDuckLake(
            catalog=f"sqlite:{tmp_path / 'catalog.sqlite'}",
            data_path=f"{scheme}://bucket/datasets/",
        )

    def test_endpoint_implies_path_style_and_derives_ssl_from_the_scheme(self):
        assert _S3Settings(
            endpoint="http://minio:9000", access_key_id="k", secret_access_key="s"
        ).sql() == (
            "TYPE s3, KEY_ID 'k', SECRET 's', ENDPOINT 'minio:9000', "
            "URL_STYLE 'path', USE_SSL false, REGION 'us-east-1'"
        )
        assert (
            "USE_SSL true"
            in _S3Settings(endpoint="https://s3.example.com", access_key_id="k").sql()
        )

    def test_scheme_less_endpoint_requires_an_explicit_ssl_choice(self):
        with pytest.raises(ValueError, match="scheme or set s3_use_ssl"):
            _S3Settings(endpoint="minio:9000")

        sql = _S3Settings(endpoint="minio:9000", use_ssl=False).sql()
        assert "ENDPOINT 'minio:9000'" in sql
        assert "USE_SSL false" in sql

    def test_explicit_settings_win_over_what_the_scheme_implies(self):
        sql = _S3Settings(
            endpoint="http://minio:9000",
            url_style="vhost",
            use_ssl=True,
            region="eu-west-3",
        ).sql()
        assert "URL_STYLE 'vhost'" in sql
        assert "USE_SSL true" in sql
        assert "REGION 'eu-west-3'" in sql

    def test_no_endpoint_leaves_duckdb_defaults_alone(self):
        assert _S3Settings(access_key_id="k", secret_access_key="s").sql() == (
            "TYPE s3, KEY_ID 'k', SECRET 's', REGION 'us-east-1'"
        )

    def test_credentials_are_escaped_not_interpolated(self):
        assert "SECRET 'pa''ss'" in _S3Settings(secret_access_key="pa'ss").sql()

    def test_settings_are_inert_until_something_is_configured(self):
        assert _S3Settings().configured is False
        assert _S3Settings(access_key_id="k").configured is True

    def test_s3_settings_on_a_local_data_path_are_rejected(self, tmp_path):
        """Silently ignoring them would leave the store unreachable at write time."""
        with pytest.raises(ValueError, match="not an object store URI"):
            DatasetSecondaryAdapterDuckLake(
                catalog=f"sqlite:{tmp_path / 'catalog.sqlite'}",
                data_path=str(tmp_path / "data"),
                s3_endpoint="http://minio:9000",
            )

    def test_a_local_data_path_still_needs_no_object_store_setup(self, tmp_path):
        adapter = DatasetSecondaryAdapterDuckLake(
            catalog=f"sqlite:{tmp_path / 'catalog.sqlite'}",
            data_path=str(tmp_path / "data"),
        )
        adapter.create(
            DatasetSpec(name="plain", columns=(ColumnSpec(name="id", type="integer"),))
        )
        adapter.write("plain", [{"id": 1}])
        assert adapter.query("SELECT id FROM plain").rows == [{"id": 1}]


def test_query_stream_fetches_rows_in_batches_not_through_query(tmp_path, monkeypatch):
    from naas_abi_core.services.dataset.adapters.secondary import (
        DatasetSecondaryAdapterDuckLake as module,
    )

    adapter = DatasetSecondaryAdapterDuckLake(
        catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
        data_path=str(tmp_path / "datasets"),
    )
    adapter.create(
        DatasetSpec(
            name="events",
            columns=(
                ColumnSpec(name="id", type="integer"),
                ColumnSpec(name="payload", type="json"),
            ),
        )
    )
    adapter.write("events", [{"id": n, "payload": {"n": n}} for n in range(2500)])
    monkeypatch.setattr(module, "FETCH_ROWS", 1000)
    monkeypatch.setattr(
        adapter,
        "query",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("materialized")),
    )

    with adapter.query_stream("SELECT id, payload FROM events ORDER BY id") as result:
        assert result.columns == ["id", "payload"]
        rows = iter(result.rows)
        assert next(rows) == {"id": 0, "payload": {"n": 0}}
        assert sum(1 for _ in rows) == 2499


def test_query_stream_rows_equal_query_rows_for_every_kind_of_value(tmp_path):
    """The stream reads its rows back from a spool; that must not change a
    value, a key's order, or which of two same-named columns wins."""
    adapter = DatasetSecondaryAdapterDuckLake(
        catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
        data_path=str(tmp_path / "datasets"),
    )
    adapter.create(
        DatasetSpec(name="seed", columns=(ColumnSpec(name="id", type="integer"),))
    )
    sql = (
        "SELECT 1180591620717411303425::HUGEINT AS huge, 0.1::DOUBLE AS ratio, "
        "CAST('NaN' AS DOUBLE) AS nan, 12.5::DECIMAL(10, 2) AS price, "
        "'0b9f2a5e-1c3d-4e5f-8a9b-0c1d2e3f4a5b'::UUID AS uid, "
        "INTERVAL 1 DAY AS span, '\\x00\\xff'::BLOB AS raw, TIME '12:30:00' AS at, "
        "TIMESTAMPTZ '2026-10-06 12:00:00+00' AS tz, [1, NULL, 3] AS list, "
        "{'a': 1, 'b': [true, NULL]} AS struct, MAP {'k': 'v'} AS map, "
        """'{"z": 1, "a": [1.5, null], "big": 1180591620717411303425}'::JSON AS doc, """
        """'café' || chr(10) || '"' AS text, NULL AS nothing, 1 AS dup, 2 AS dup"""
    )

    (row,) = adapter.query(sql).rows
    with adapter.query_stream(sql) as result:
        (streamed,) = list(result.rows)

    assert list(streamed.items()) == list(row.items())
    assert streamed["huge"] == 2**70 + 1 and streamed["dup"] == 2
    assert list(streamed["doc"]) == ["z", "a", "big"]


def test_query_stream_spools_one_batch_at_a_time(tmp_path, monkeypatch):
    """Rows are spooled FETCH_ROWS at a time and read back lazily: Python
    memory holds about one batch (0.8 MiB here), never the whole result
    (20 MiB when the spool fetched it all at once)."""
    import tracemalloc

    from naas_abi_core.services.dataset.adapters.secondary import (
        DatasetSecondaryAdapterDuckLake as module,
    )

    monkeypatch.setattr(module, "FETCH_ROWS", 100)
    adapter = DatasetSecondaryAdapterDuckLake(
        catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
        data_path=str(tmp_path / "datasets"),
    )
    adapter.create(
        DatasetSpec(name="seed", columns=(ColumnSpec(name="id", type="integer"),))
    )
    adapter.describe("seed")  # attach the read connection before measuring
    sql = "SELECT range AS n, repeat('x', 4000) AS pad FROM range(5000)"  # 20 MB

    tracemalloc.start()
    try:
        with adapter.query_stream(sql) as result:
            count = sum(1 for _ in result.rows)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

    assert count == 5000
    assert peak < 5 * 1024 * 1024


def test_query_stream_removes_its_spool_on_early_exit_and_on_error(
    tmp_path, monkeypatch
):
    import tempfile

    spool_dir = tmp_path / "spool"
    spool_dir.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spool_dir))
    spools = []
    temporary_file = tempfile.TemporaryFile

    def tracked(*args, **kwargs):
        spools.append(temporary_file(*args, **kwargs))
        return spools[-1]

    monkeypatch.setattr(tempfile, "TemporaryFile", tracked)
    adapter = DatasetSecondaryAdapterDuckLake(
        catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
        data_path=str(tmp_path / "datasets"),
    )
    adapter.create(
        DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
    )
    adapter.write("events", [{"id": n} for n in range(10)])

    with adapter.query_stream("SELECT id FROM events") as result:
        next(iter(result.rows))  # leaves with rows unread
    with (
        pytest.raises(RuntimeError, match="reader failed"),
        adapter.query_stream("SELECT id FROM events"),
    ):
        raise RuntimeError("reader failed")
    with (
        pytest.raises(Exception, match="does not exist"),
        adapter.query_stream("SELECT id FROM missing"),
    ):
        pass  # fails while spooling

    assert len(spools) >= 2 and all(spool.closed for spool in spools)
    assert list(spool_dir.iterdir()) == []


def test_sqlite_catalog_survives_concurrent_reads_and_writes(tmp_path):
    """Reads overlapping writes on a SQLite catalog used to leave DuckDB holding
    a lock for good: every later read failed with "database is locked", even
    from a new adapter in the same process (module jobs hit it in the engine)."""
    import random
    import threading
    import time

    adapter = DatasetSecondaryAdapterDuckLake(
        catalog=f"sqlite:{tmp_path / 'catalog.sqlite'}",
        data_path=str(tmp_path / "data"),
        retry_base_delay_seconds=0.01,
    )
    columns = (
        ColumnSpec(name="id", type="string"),
        ColumnSpec(name="v", type="string"),
    )
    for ns in "abc":
        adapter.create(
            DatasetSpec(name="t", namespace=ns, columns=columns, primary_key=("id",))
        )
    errors: list[str] = []
    stop = time.monotonic() + 4

    def write(ns: str) -> None:
        n = 0
        while time.monotonic() < stop:
            try:
                adapter.write(
                    "t", [{"id": f"{n % 20}", "v": "x"}], namespace=ns, mode="upsert"
                )
            except Exception as exc:  # noqa: BLE001 - collected for the assertion
                errors.append(f"write: {exc}")
            n += 1
            time.sleep(random.uniform(0, 0.05))

    def read(ns: str) -> None:
        while time.monotonic() < stop:
            try:
                adapter.describe("t", namespace=ns)
                adapter.query("SELECT count(*) AS n FROM t", namespace=ns)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"read: {exc}")

    def monitor(ns: str) -> None:
        # The catalog monitor job reads inlined row counts while writes go on.
        while time.monotonic() < stop:
            try:
                adapter.inlined_row_count("t", namespace=ns)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"inlined_row_count: {exc}")

    threads = [threading.Thread(target=write, args=(ns,)) for ns in "abc"]
    threads += [
        threading.Thread(target=read, args=(ns,)) for ns in "abc" for _ in range(2)
    ]
    threads += [threading.Thread(target=monitor, args=(ns,)) for ns in "ab"]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert adapter.describe("t", namespace="a").name == "t"  # not locked afterwards


def test_inlined_row_count_waits_for_a_write_on_a_sqlite_catalog(tmp_path):
    """Every catalog access holds the catalog lock: a read outside it that
    overlapped a write left DuckDB holding a SQLite lock for good."""
    import threading

    adapter = DatasetSecondaryAdapterDuckLake(
        catalog=f"sqlite:{tmp_path / 'catalog.sqlite'}",
        data_path=str(tmp_path / "data"),
    )
    adapter.create(
        DatasetSpec(
            name="t",
            columns=(ColumnSpec(name="id", type="string"),),
            primary_key=("id",),
        )
    )
    adapter.write("t", [{"id": "1"}], mode="upsert")
    counts: list[int] = []

    with adapter._catalog_lock.exclusive():
        reader = threading.Thread(target=lambda: counts.append(adapter.inlined_row_count("t")))
        reader.start()
        reader.join(timeout=0.3)
        assert reader.is_alive(), "inlined_row_count read the catalog during a write"

    reader.join(timeout=10)
    assert not reader.is_alive() and len(counts) == 1  # runs once the write is done


# --- compaction and snapshot expiry ---------------------------------------------------


def _files(adapter: DatasetSecondaryAdapterDuckLake, data_path) -> dict[str, int]:
    """Live data and delete files, files waiting for deletion, snapshots, and
    Parquet files on disk."""
    metadata = f'"__ducklake_metadata_{CATALOG_ALIAS}"'
    queries = {
        "data": f"SELECT count(*) FROM {metadata}.ducklake_data_file WHERE end_snapshot IS NULL",
        "deletes": f"SELECT count(*) FROM {metadata}.ducklake_delete_file WHERE end_snapshot IS NULL",
        "scheduled": f"SELECT count(*) FROM {metadata}.ducklake_files_scheduled_for_deletion",
        "snapshots": f"SELECT count(*) FROM {metadata}.ducklake_snapshot",
    }
    con = adapter._connect()
    try:
        counts = {key: con.execute(sql).fetchone()[0] for key, sql in queries.items()}
    finally:
        con.close()
    counts["on_disk"] = sum(1 for _ in data_path.rglob("*.parquet"))
    return counts


def _upserted_table(tmp_path, **options) -> DatasetSecondaryAdapterDuckLake:
    """A table written like the signal pulls: one full load, then daily upserts
    touching a few rows, each leaving a data file and a delete file."""
    adapter = DatasetSecondaryAdapterDuckLake(
        catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
        data_path=str(tmp_path / "datasets"),
        data_inlining_row_limit=0,
        **options,
    )
    adapter.create(
        DatasetSpec(
            name="messages",
            columns=(
                ColumnSpec(name="id", type="integer"),
                ColumnSpec(name="subject", type="string"),
            ),
            primary_key=("id",),
        )
    )
    adapter.write(
        "messages",
        [{"id": n, "subject": f"first-{n}"} for n in range(1000)],
        mode="replace",
    )
    for day in range(6):
        adapter.write(
            "messages",
            [{"id": n, "subject": f"day{day}-{n}"} for n in range(day * 10, day * 10 + 5)]
            + [{"id": 5000 + day, "subject": "new"}],
            mode="upsert",
        )
    return adapter


def _contents(adapter: DatasetSecondaryAdapterDuckLake) -> list[dict]:
    return adapter.query("SELECT id, subject FROM messages ORDER BY id").rows


def test_compaction_rewrites_files_with_deletes(tmp_path):
    adapter = _upserted_table(tmp_path)
    before = _files(adapter, tmp_path / "datasets")
    rows = _contents(adapter)
    assert before["deletes"] == 1 and before["data"] > 1

    result = adapter.compact("messages")

    after = _files(adapter, tmp_path / "datasets")
    assert (after["data"], after["deletes"]) == (1, 0)
    assert _contents(adapter) == rows
    assert result.columns[0] == "step"
    steps = {row["step"]: row for row in result.rows}
    assert steps["rewrite"]["files_processed"] == 1
    assert steps["merge"]["files_processed"] == before["data"]
    assert steps["merge"]["files_created"] == 1
    # The replaced files wait for clean_up; nothing is deleted yet.
    assert after["scheduled"] > before["scheduled"]
    assert after["on_disk"] >= before["on_disk"]


def test_compaction_leaves_files_below_the_delete_threshold(tmp_path):
    adapter = _upserted_table(tmp_path, compaction_delete_threshold=0.5)

    adapter.compact("messages")

    # 30 deleted rows of 1000 are below half: the big file keeps its deletes.
    assert _files(adapter, tmp_path / "datasets")["deletes"] == 1


def test_clean_up_deletes_replaced_files_and_keeps_every_snapshot(
    tmp_path, monkeypatch
):
    adapter = _upserted_table(tmp_path)
    query = "SELECT count(*) AS n, max(subject) AS last FROM messages"
    history = {
        snapshot.snapshot_id: adapter.query(query, snapshot_id=snapshot.snapshot_id).rows
        for snapshot in adapter.list_snapshots()[2:]
    }
    adapter.compact("messages")
    compacted = _files(adapter, tmp_path / "datasets")

    dry = adapter.clean_up(dry_run=True)
    assert dry == {
        "dry_run": True,
        "retention_days": None,
        "snapshots_expired": 0,
        "files_deleted": compacted["scheduled"],
    }
    assert _files(adapter, tmp_path / "datasets") == compacted

    # A SQLite catalog does not honour the grace (local catalogs only).
    monkeypatch.setattr(ducklake_module, "CLEANUP_GRACE", timedelta(0))
    report = adapter.clean_up()

    cleaned = _files(adapter, tmp_path / "datasets")
    assert report["files_deleted"] == compacted["scheduled"] > 0
    assert cleaned["scheduled"] == 0
    assert cleaned["on_disk"] == compacted["on_disk"] - compacted["scheduled"]
    assert cleaned["snapshots"] == compacted["snapshots"]
    adapter._snapshot_connections.clear()
    for snapshot_id, rows in history.items():
        assert adapter.query(query, snapshot_id=snapshot_id).rows == rows


def test_clean_up_expires_snapshots_past_the_retention(tmp_path, monkeypatch):
    adapter = _upserted_table(tmp_path, snapshot_retention_days=0)
    adapter.compact("messages")
    rows = _contents(adapter)
    snapshots = _files(adapter, tmp_path / "datasets")["snapshots"]

    dry = adapter.clean_up(dry_run=True)
    assert dry["snapshots_expired"] == snapshots - 1
    assert _files(adapter, tmp_path / "datasets")["snapshots"] == snapshots

    monkeypatch.setattr(ducklake_module, "CLEANUP_GRACE", timedelta(0))
    report = adapter.clean_up()

    cleaned = _files(adapter, tmp_path / "datasets")
    assert report["retention_days"] == 0
    assert report["snapshots_expired"] == snapshots - 1
    assert cleaned["snapshots"] == 1
    assert cleaned["on_disk"] == 1 and cleaned["scheduled"] == 0
    assert _contents(adapter) == rows


def test_maintenance_options_are_checked(tmp_path):
    for options in ({"snapshot_retention_days": -1}, {"compaction_delete_threshold": 2}):
        with pytest.raises(ValueError):
            DatasetSecondaryAdapterDuckLake(
                catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
                data_path=str(tmp_path / "datasets"),
                **options,
            )


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("ABI_TEST_DUCKLAKE_POSTGRES") != "1",
    reason="set ABI_TEST_DUCKLAKE_POSTGRES=1 to run the PostgreSQL catalog test",
)
def test_postgres_catalog_clean_up_waits_out_the_grace(tmp_path, monkeypatch):
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(
        "postgres:16-alpine",
        username="ducklake",
        password="ducklake",
        dbname="ducklake",
    ) as postgres:
        catalog = f"postgres:{postgres.get_connection_url(driver=None)}"
        data_path = tmp_path / "datasets"
        adapter = DatasetSecondaryAdapterDuckLake(
            catalog=catalog, data_path=str(data_path), data_inlining_row_limit=0
        )
        adapter.create(
            DatasetSpec(name="events", columns=(ColumnSpec(name="id", type="integer"),))
        )
        for _ in range(3):
            adapter.write("events", [{"id": n} for n in range(100)], mode="replace")
        for n in range(3):
            adapter.write("events", [{"id": 100 + n}])
        adapter.compact("events")
        scheduled = _files(adapter, data_path)["scheduled"]
        assert scheduled > 0

        # Files scheduled within the grace stay, for reads still using them.
        assert adapter.clean_up()["files_deleted"] == 0

        monkeypatch.setattr(ducklake_module, "CLEANUP_GRACE", timedelta(0))
        assert adapter.clean_up()["files_deleted"] == scheduled
        assert _files(adapter, data_path)["scheduled"] == 0
        assert adapter.query("SELECT count(*) AS n FROM events").rows == [{"n": 103}]
