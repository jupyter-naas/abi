from abc import ABC, abstractmethod

import pytest
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetAlreadyExistsError,
    DatasetNotFoundError,
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
        )

    def test_create_describe_list_and_query(self, adapter: IDatasetPort):
        created = adapter.create(self._spec())
        assert created.name == "github_commits"
        assert created.namespace == "acme"
        described = adapter.describe("github_commits", namespace="acme")
        assert described.snapshot_id == created.snapshot_id
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
            "WHERE author_date_month = '2026-08' AND project_id = 'p1'",
            namespace="acme",
        )
        assert august.rows[0]["added"] == 10

    def test_replace_overwrites_rows(self, adapter: IDatasetPort):
        adapter.create(self._spec())
        adapter.write(
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
