from abc import ABC, abstractmethod

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

        historical = adapter.query(
            "SELECT c.sha, p.label FROM github_commits c "
            "JOIN projects p USING (project_id) ORDER BY c.sha",
            namespace="acme",
            snapshot_id=coherent_snapshot.snapshot_id,
        )
        assert historical.rows == [{"sha": "old", "label": "before"}]
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
