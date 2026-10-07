from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pytest
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetAlreadyExistsError,
    DatasetNotFoundError,
    DatasetSchemaError,
    DatasetSnapshotConflictError,
    DatasetSnapshotNotFoundError,
    DatasetSpec,
    IDatasetPort,
    PartitionSpec,
)


class DatasetSecondaryAdapterContract(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter(self) -> IDatasetPort:
        raise NotImplementedError()

    def _spec(self) -> DatasetSpec:
        return DatasetSpec(
            name="github_commits",
            namespace="acme",
            columns=(
                ColumnSpec(name="sha", type="string"),
                ColumnSpec(name="project_id", type="string"),
                ColumnSpec(name="author_date", type="date"),
                ColumnSpec(name="additions", type="integer"),
                ColumnSpec(name="deletions", type="integer"),
            ),
            partitions=(
                PartitionSpec(column="project_id", transform="identity"),
                PartitionSpec(column="author_date", transform="month"),
            ),
            primary_key=("sha",),
        )

    def test_create_describe_list_and_query(self, adapter: IDatasetPort):
        created = adapter.create(self._spec())
        assert isinstance(created.snapshot_id, int)
        assert created.name == "github_commits"
        assert created.namespace == "acme"
        described = adapter.describe("github_commits", namespace="acme")
        assert described.snapshot_id == created.snapshot_id
        assert described.primary_key == ("sha",)
        listed = adapter.list(namespace="acme")
        assert [item.name for item in listed] == ["github_commits"]

        written = adapter.write(
            "github_commits",
            [
                {
                    "sha": "aaa",
                    "project_id": "p1",
                    "author_date": "2026-08-02",
                    "additions": 10,
                    "deletions": 2,
                },
                {
                    "sha": "bbb",
                    "project_id": "p1",
                    "author_date": "2026-07-15",
                    "additions": 4,
                    "deletions": 1,
                },
                {
                    "sha": "ccc",
                    "project_id": "p2",
                    "author_date": "2026-08-20",
                    "additions": 7,
                    "deletions": 0,
                },
            ],
            namespace="acme",
        )
        assert written.snapshot_id != created.snapshot_id

        total = adapter.query(
            "SELECT SUM(additions) AS added FROM github_commits",
            namespace="acme",
        )
        assert total.rows[0]["added"] == 21

        august = adapter.query(
            "SELECT SUM(additions) AS added FROM github_commits "
            "WHERE month(author_date) = 8 AND project_id = 'p1'",
            namespace="acme",
        )
        assert august.rows[0]["added"] == 10

    def test_repeated_partitioned_appends_preserve_existing_and_new_partitions(
        self, adapter: IDatasetPort
    ):
        adapter.create(self._spec())
        batches = [
            ("one", "p1", "2026-08-01"),
            ("two", "p1", "2026-08-02"),
            ("three", "p2", "2026-09-01"),
        ]
        for sha, project_id, author_date in batches:
            adapter.write(
                "github_commits",
                [
                    {
                        "sha": sha,
                        "project_id": project_id,
                        "author_date": author_date,
                        "additions": 1,
                        "deletions": 0,
                    }
                ],
                namespace="acme",
            )

        result = adapter.query(
            "SELECT sha FROM github_commits ORDER BY sha", namespace="acme"
        )
        assert [row["sha"] for row in result.rows] == ["one", "three", "two"]

    def test_replace_overwrites_rows(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        old_snapshot = adapter.write(
            "github_commits",
            [
                {
                    "sha": "old",
                    "project_id": "p1",
                    "author_date": "2026-08-01",
                    "additions": 100,
                    "deletions": 0,
                }
            ],
            namespace="acme",
        )
        adapter.write(
            "github_commits",
            [
                {
                    "sha": "new",
                    "project_id": "p1",
                    "author_date": "2026-08-01",
                    "additions": 1,
                    "deletions": 0,
                }
            ],
            namespace="acme",
            mode="replace",
        )
        result = adapter.query(
            "SELECT sha, additions FROM github_commits ORDER BY sha",
            namespace="acme",
        )
        assert [row["sha"] for row in result.rows] == ["new"]
        assert result.rows[0]["additions"] == 1
        historical = adapter.query(
            "SELECT sha, additions FROM github_commits",
            namespace="acme",
            snapshot_id=old_snapshot.snapshot_id,
        )
        assert historical.rows == [{"sha": "old", "additions": 100}]

    def test_replace_with_empty_rows_clears_dataset(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        populated = adapter.write(
            "github_commits",
            [
                {
                    "sha": "old",
                    "project_id": "p1",
                    "author_date": "2026-08-01",
                    "additions": 1,
                    "deletions": 0,
                }
            ],
            namespace="acme",
        )

        emptied = adapter.write("github_commits", [], namespace="acme", mode="replace")

        assert emptied.snapshot_id != populated.snapshot_id
        assert (
            adapter.query("SELECT * FROM github_commits", namespace="acme").rows == []
        )
        assert adapter.query(
            "SELECT sha FROM github_commits",
            namespace="acme",
            snapshot_id=populated.snapshot_id,
        ).rows == [{"sha": "old"}]

    def test_stale_write_snapshot_raises_conflict(self, adapter: IDatasetPort):
        stale = adapter.create(self._spec())
        current = adapter.create(
            DatasetSpec(
                name="projects",
                namespace="acme",
                columns=(ColumnSpec(name="id", type="string"),),
            )
        )

        with pytest.raises(DatasetSnapshotConflictError) as raised:
            adapter.write(
                "github_commits",
                [],
                namespace="acme",
                snapshot_id=stale.snapshot_id,
            )

        assert raised.value.expected_snapshot_id == stale.snapshot_id
        assert raised.value.current_snapshot_id == current.snapshot_id

    def test_json_round_trips_and_is_queryable(self, adapter: IDatasetPort):
        spec = DatasetSpec(
            name="events",
            namespace="acme",
            columns=(
                ColumnSpec(name="id", type="string"),
                ColumnSpec(name="payload", type="json"),
            ),
            primary_key=("id",),
        )
        adapter.create(spec)
        adapter.write(
            "events",
            [{"id": "one", "payload": {"nested": {"answer": 42}, "ok": True}}],
            namespace="acme",
        )

        result = adapter.query(
            "SELECT payload, payload->>'$.nested.answer' AS answer FROM events",
            namespace="acme",
        )
        assert result.rows == [
            {
                "payload": {"nested": {"answer": 42}, "ok": True},
                "answer": "42",
            }
        ]

        with pytest.raises(DatasetSchemaError, match="not valid JSON"):
            adapter.write(
                "events",
                [{"id": "two", "payload": "{broken"}],
                namespace="acme",
            )

    def test_upsert_updates_inserts_and_moves_partition_keys(
        self, adapter: IDatasetPort
    ):
        adapter.create(self._spec())
        adapter.write(
            "github_commits",
            [
                {
                    "sha": "existing",
                    "project_id": "old_partition",
                    "author_date": "2026-08-01",
                    "additions": 1,
                    "deletions": 0,
                }
            ],
            namespace="acme",
        )
        adapter.write(
            "github_commits",
            [
                {
                    "sha": "existing",
                    "project_id": "new_partition",
                    "author_date": "2026-09-01",
                    "additions": 5,
                    "deletions": 1,
                },
                {
                    "sha": "new",
                    "project_id": "new_partition",
                    "author_date": "2026-09-02",
                    "additions": 2,
                    "deletions": 0,
                },
            ],
            namespace="acme",
            mode="upsert",
        )

        result = adapter.query(
            "SELECT sha, project_id, additions FROM github_commits ORDER BY sha",
            namespace="acme",
        )
        assert result.rows == [
            {"sha": "existing", "project_id": "new_partition", "additions": 5},
            {"sha": "new", "project_id": "new_partition", "additions": 2},
        ]

    def test_upsert_rejects_null_and_duplicate_incoming_keys(
        self, adapter: IDatasetPort
    ):
        adapter.create(self._spec())
        base = {
            "project_id": "p1",
            "author_date": "2026-08-01",
            "additions": 1,
            "deletions": 0,
        }
        with pytest.raises(DatasetSchemaError, match="null primary key"):
            adapter.write(
                "github_commits",
                [{"sha": None, **base}],
                namespace="acme",
                mode="upsert",
            )
        with pytest.raises(DatasetSchemaError, match="duplicate primary key"):
            adapter.write(
                "github_commits",
                [{"sha": "same", **base}, {"sha": "same", **base}],
                namespace="acme",
                mode="upsert",
            )

    def test_snapshots_support_catalog_wide_time_travel(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        adapter.write(
            "github_commits",
            [
                {
                    "sha": "old",
                    "project_id": "p1",
                    "author_date": "2026-08-01",
                    "additions": 1,
                    "deletions": 0,
                }
            ],
            namespace="acme",
        )
        adapter.create(
            DatasetSpec(
                name="projects",
                namespace="acme",
                columns=(
                    ColumnSpec(name="project_id", type="string"),
                    ColumnSpec(name="label", type="string"),
                ),
                primary_key=("project_id",),
            )
        )
        coherent_snapshot = adapter.write(
            "projects",
            [{"project_id": "p1", "label": "before"}],
            namespace="acme",
        )
        adapter.write(
            "github_commits",
            [
                {
                    "sha": "new",
                    "project_id": "p1",
                    "author_date": "2026-08-02",
                    "additions": 2,
                    "deletions": 0,
                }
            ],
            namespace="acme",
        )
        adapter.write(
            "projects",
            [{"project_id": "p1", "label": "after"}],
            namespace="acme",
            mode="upsert",
        )

        sql = (
            "SELECT c.sha, p.label FROM github_commits c "
            "JOIN projects p USING (project_id) ORDER BY c.sha"
        )
        historical = adapter.query(
            sql, namespace="acme", snapshot_id=coherent_snapshot.snapshot_id
        )
        assert historical.rows == [{"sha": "old", "label": "before"}]
        with adapter.query_stream(
            sql, namespace="acme", snapshot_id=coherent_snapshot.snapshot_id
        ) as streamed:
            assert list(streamed.rows) == historical.rows
        snapshots = adapter.list_snapshots()
        assert [item.snapshot_id for item in snapshots] == sorted(
            item.snapshot_id for item in snapshots
        )
        assert coherent_snapshot.snapshot_id in {item.snapshot_id for item in snapshots}
        with pytest.raises(DatasetSnapshotNotFoundError):
            adapter.query(
                "SELECT * FROM github_commits",
                namespace="acme",
                snapshot_id=max(item.snapshot_id for item in snapshots) + 100,
            )

    def test_create_duplicate_and_missing(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        with pytest.raises(DatasetAlreadyExistsError):
            adapter.create(self._spec())
        with pytest.raises(DatasetNotFoundError):
            adapter.describe("missing", namespace="acme")

    def test_drop_removes_dataset(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        adapter.drop("github_commits", namespace="acme")
        with pytest.raises(DatasetNotFoundError):
            adapter.describe("github_commits", namespace="acme")
        assert adapter.list(namespace="acme") == []

    def test_long_operations_accept_a_callers_deadline(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        adapter.write(
            "github_commits",
            [
                {
                    "sha": "a",
                    "project_id": "p",
                    "author_date": "2026-08-02",
                    "additions": 1,
                    "deletions": 0,
                }
            ],
            namespace="acme",
        )

        adapter.flush("github_commits", namespace="acme", timeout_seconds=60.0)
        adapter.compact("github_commits", namespace="acme", timeout_seconds=60.0)
        result = adapter.query(
            "SELECT sha FROM github_commits", namespace="acme", timeout_seconds=60.0
        )

        assert result.rows == [{"sha": "a"}]

    # --- streamed reads (docs/adr/20261003_nats-streamed-results.md)

    def test_query_stream_reads_the_rows_query_returns(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        adapter.write(
            "github_commits",
            [
                {
                    "sha": f"{n:05d}",
                    "project_id": f"p{n % 3}",
                    "author_date": "2026-08-02",
                    "additions": n,
                    "deletions": None if n % 7 == 0 else 1,
                }
                for n in range(2500)  # more than one fetch batch and one frame
            ],
            namespace="acme",
        )
        sql = "SELECT sha, additions, deletions FROM github_commits ORDER BY sha"

        with adapter.query_stream(sql, namespace="acme") as result:
            assert result.columns == ["sha", "additions", "deletions"]
            streamed = list(result.rows)

        assert streamed == adapter.query(sql, namespace="acme").rows
        assert len(streamed) == 2500

    def test_query_stream_of_a_missing_table_raises_before_any_row(
        self, adapter: IDatasetPort
    ):
        with (
            pytest.raises(Exception),
            adapter.query_stream(
                "SELECT * FROM no_such_table", namespace="acme"
            ) as result,
        ):
            list(result.rows)

    def test_an_unread_query_stream_holds_up_neither_writes_nor_reads(
        self, adapter: IDatasetPort
    ):
        """A stream its reader stopped reading (an export whose browser went
        away; its transfer only expires after 60 s idle) must not block the
        catalog: a write made meanwhile finishes, then reads do. The stream
        keeps the rows of the snapshot it opened on."""
        adapter.create(self._spec())
        adapter.write("github_commits", list(self._commits(3)), namespace="acme")
        # Several MiB, more than the transfer buffers hold: over NATS the
        # producer waits on this reader.
        sql = (
            "SELECT c.sha, r.range AS n, repeat('x', 100) AS pad "
            "FROM github_commits c, range(20000) r"
        )

        def write_then_read() -> tuple[int, int]:
            adapter.write(
                "github_commits", list(self._commits(1, start=3)), namespace="acme"
            )
            adapter.describe("github_commits", namespace="acme")
            return self._totals(adapter)

        # The stream exits first, so a blocked write is released on failure.
        with (
            ThreadPoolExecutor(max_workers=1) as pool,
            adapter.query_stream(sql, namespace="acme") as result,
        ):
            assert pool.submit(write_then_read).result(timeout=10) == (4, 6)
            assert sum(1 for _ in result.rows) == 3 * 20000

    def test_integers_round_trip_exactly_and_stay_integers(self, adapter: IDatasetPort):
        big = 2**60 + 1  # not representable as a double
        adapter.create(
            DatasetSpec(
                name="measures",
                namespace="acme",
                columns=(
                    ColumnSpec(name="id", type="bigint"),
                    ColumnSpec(name="count", type="integer"),
                    ColumnSpec(name="ratio", type="double"),
                    ColumnSpec(name="payload", type="json"),
                ),
            )
        )
        adapter.write(
            "measures",
            [
                {
                    "id": big,
                    "count": 42,
                    "ratio": 1.0,
                    "payload": {"n": 42, "big": big, "f": 1.5},
                }
            ],
            namespace="acme",
        )
        sql = "SELECT id, count, ratio, payload FROM measures"

        (row,) = adapter.query(sql, namespace="acme").rows
        with adapter.query_stream(sql, namespace="acme") as result:
            (streamed,) = list(result.rows)

        for got in (row, streamed):
            assert got["id"] == big and type(got["id"]) is int
            assert got["count"] == 42 and type(got["count"]) is int
            assert got["ratio"] == 1.0 and type(got["ratio"]) is float
            assert got["payload"] == {"n": 42, "big": big, "f": 1.5}
            assert type(got["payload"]["n"]) is int

    def test_rows_hold_the_same_portable_values_on_every_adapter(
        self, adapter: IDatasetPort
    ):
        # The value rules in DatasetPort.QueryResult, whatever the backend.
        adapter.create(
            DatasetSpec(
                name="readings",
                namespace="acme",
                columns=(
                    ColumnSpec(name="read_on", type="date"),
                    ColumnSpec(name="read_at", type="timestamp"),
                    ColumnSpec(name="ok", type="boolean"),
                    ColumnSpec(name="label", type="string"),
                ),
            )
        )
        adapter.write(
            "readings",
            [
                {
                    "read_on": date(2026, 10, 4),
                    "read_at": datetime(2026, 10, 4, 12, 30),  # noqa: DTZ001 - naive on purpose
                    "ok": True,
                    "label": "café",
                }
            ],
            namespace="acme",
        )
        sql = (
            "SELECT read_on, read_at, ok, label, CAST(1.25 AS DECIMAL(3, 2)) AS price, "
            "CAST('NaN' AS DOUBLE) AS nan, CAST('Infinity' AS DOUBLE) AS inf "
            "FROM readings"
        )

        (row,) = adapter.query(sql, namespace="acme").rows
        with adapter.query_stream(sql, namespace="acme") as result:
            (streamed,) = list(result.rows)

        expected = {
            "read_on": "2026-10-04",
            "read_at": "2026-10-04T12:30:00",
            "ok": True,
            "label": "café",
            "price": 1.25,
            "nan": None,
            "inf": None,
        }
        assert row == expected and streamed == expected
        assert type(row["price"]) is float

    @pytest.mark.parametrize("value", [float("nan"), float("inf")])
    def test_non_finite_numbers_are_refused_on_write(
        self, adapter: IDatasetPort, value: float
    ):
        adapter.create(
            DatasetSpec(
                name="ratios",
                namespace="acme",
                columns=(ColumnSpec(name="ratio", type="double"),),
            )
        )

        with pytest.raises(DatasetSchemaError, match="finite"):
            adapter.write("ratios", [{"ratio": value}], namespace="acme")

        assert adapter.query("SELECT * FROM ratios", namespace="acme").rows == []

    # ------------------------------------------------------------------
    # write_stream: an iterator of rows, committed once.
    # ------------------------------------------------------------------

    def _commits(self, count: int, start: int = 0):
        for n in range(start, start + count):
            yield {
                "sha": f"c{n:06d}",
                "project_id": "p1",
                "author_date": "2026-08-02",
                "additions": n,
                "deletions": 1,
            }

    def _totals(self, adapter: IDatasetPort) -> tuple[int, int]:
        (row,) = adapter.query(
            "SELECT count(*) AS n, coalesce(sum(additions), 0) AS total "
            "FROM github_commits",
            namespace="acme",
        ).rows
        return row["n"], row["total"]

    def test_write_stream_commits_an_iterator_once(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        before = len(adapter.list_snapshots())

        info = adapter.write_stream(
            "github_commits", self._commits(25_000), namespace="acme"
        )

        assert self._totals(adapter) == (25_000, sum(range(25_000)))
        assert len(adapter.list_snapshots()) == before + 1
        assert (
            info.snapshot_id
            == adapter.describe("github_commits", namespace="acme").snapshot_id
        )

    def test_write_stream_replaces_and_upserts(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        adapter.write_stream("github_commits", self._commits(10), namespace="acme")

        adapter.write_stream(
            "github_commits", self._commits(5, start=8), namespace="acme", mode="upsert"
        )
        assert self._totals(adapter) == (13, sum(range(13)))

        adapter.write_stream(
            "github_commits", self._commits(3), namespace="acme", mode="replace"
        )
        assert self._totals(adapter) == (3, 3)

        adapter.write_stream(
            "github_commits", iter(()), namespace="acme", mode="replace"
        )
        assert self._totals(adapter) == (0, 0)

    @pytest.mark.parametrize(
        ("bad", "match"),
        [
            ({"sha": "c000010"}, "duplicate primary key"),  # earlier in the stream
            ({"sha": None}, "null primary key"),
            ({"additions": float("nan")}, "finite"),
            ({"extra": 1}, "unknown columns"),
        ],
    )
    def test_write_stream_is_all_or_nothing(
        self, adapter: IDatasetPort, bad: dict, match: str
    ):
        adapter.create(self._spec())
        adapter.write("github_commits", list(self._commits(2)), namespace="acme")

        def rows():
            yield from self._commits(3_000, start=10)
            yield {**next(self._commits(1, start=99_999)), **bad}

        with pytest.raises(DatasetSchemaError, match=match):
            adapter.write_stream(
                "github_commits", rows(), namespace="acme", mode="upsert"
            )

        assert self._totals(adapter) == (2, 1)

    def test_write_stream_stops_when_the_iterator_fails(self, adapter: IDatasetPort):
        adapter.create(self._spec())

        def rows():
            yield from self._commits(100)
            raise RuntimeError("source went away")

        with pytest.raises(Exception, match="source went away"):
            adapter.write_stream("github_commits", rows(), namespace="acme")

        assert self._totals(adapter) == (0, 0)

    def test_write_stream_checks_the_snapshot(self, adapter: IDatasetPort):
        created = adapter.create(self._spec())
        adapter.write("github_commits", list(self._commits(1)), namespace="acme")

        with pytest.raises(DatasetSnapshotConflictError):
            adapter.write_stream(
                "github_commits",
                self._commits(5, start=1),
                namespace="acme",
                snapshot_id=created.snapshot_id,
            )

        assert self._totals(adapter) == (1, 0)

    @pytest.mark.parametrize("streamed", [False, True])
    def test_timestamps_with_an_offset_are_stored_in_utc(
        self, adapter: IDatasetPort, streamed: bool
    ):
        adapter.create(
            DatasetSpec(
                name="visits",
                namespace="acme",
                columns=(
                    ColumnSpec(name="n", type="integer"),
                    ColumnSpec(name="seen_at", type="timestamp"),
                ),
            )
        )
        paris = timezone(timedelta(hours=2))
        rows = [
            {"n": 1, "seen_at": datetime(2026, 10, 4, 12, 30, tzinfo=paris)},
            {"n": 2, "seen_at": "2026-10-04T12:30:00+02:00"},
            {"n": 3, "seen_at": "2026-10-04T10:30:00Z"},
            {"n": 4, "seen_at": datetime(2026, 10, 4, 10, 30)},  # noqa: DTZ001 - naive: UTC
        ]
        if streamed:
            adapter.write_stream("visits", iter(rows), namespace="acme")
        else:
            adapter.write("visits", rows, namespace="acme")

        got = adapter.query(
            "SELECT n, seen_at FROM visits ORDER BY n", namespace="acme"
        )

        assert [row["seen_at"] for row in got.rows] == ["2026-10-04T10:30:00"] * 4
