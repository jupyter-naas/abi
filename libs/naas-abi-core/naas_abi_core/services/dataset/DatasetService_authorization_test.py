"""Datasets pass the authorization contract.

A query needs ``Query`` on every dataset its SQL reads, through joins,
subqueries and CTEs, and a query the check cannot vouch for is refused.
"""

from __future__ import annotations

import pytest
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.dataset.adapters.primary.dataset__primary_adapter__NATS import (
    DatasetPrimaryAdapterNATS,
)
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterDuckLake import (
    DatasetSecondaryAdapterDuckLake,
)
from naas_abi_core.services.dataset.adapters.secondary.DatasetSecondaryAdapterNATSClient import (
    DatasetSecondaryAdapterNATSClient,
)
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetNotFoundError,
    DatasetSpec,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_core.services.dataset.iam_catalog import CATALOG
from naas_abi_core.services.iam.tests.data_service_contract import (
    ANY_OK,
    DENY,
    HIDDEN,
    NOT_FOUND,
    SECRET,
    Case,
    DataServiceContract,
    Expect,
    ok,
)

INVALID = "invalid"
REFUSED_QUERY = Expect(INVALID)
COLUMNS = (ColumnSpec(name="id", type="integer"),)


def _spec(namespace: str, name: str) -> DatasetSpec:
    return DatasetSpec(name=name, namespace=namespace, columns=COLUMNS)


def _rows(result) -> list:
    return [row["n"] for row in result.rows]


def _streamed(datasets: DatasetService, sql: str, namespace: str) -> list:
    with datasets.query_stream(sql, namespace=namespace) as result:
        return [row["n"] for row in result.rows]


class TestDatasetAuthorization(DataServiceContract):
    catalog = CATALOG

    def build_owner(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        return DatasetService(
            DatasetSecondaryAdapterDuckLake(
                catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
                data_path=str(tmp_path / "datasets"),
                max_retries=10,
                retry_base_delay_seconds=0.01,
            )
        )

    def seed(self, owner):
        for namespace, name in (
            ("sales", "orders"),
            ("sales", "items"),
            ("hr", "salaries"),
            ("frozen", "f"),
        ):
            owner.create(_spec(namespace, name))
            owner.write(name, [{"id": 1}, {"id": 2}], namespace=namespace)

    def build_primary(self, owner):
        return DatasetPrimaryAdapterNATS(owner, SECRET)

    def build_remote(self, url, identity):
        return DatasetService(
            DatasetSecondaryAdapterNATSClient(url, TEST_TOKENS.source(identity))
        )

    def close_remote(self, remote):
        remote.adapter.close()

    @staticmethod
    def _namespace(namespace: str) -> list[str]:
        return [
            f"abi:-:-:dataset:namespace/{namespace}",
            f"abi:-:-:dataset:dataset/{namespace}/*",
        ]

    def granted_resources(self):
        return self._namespace("sales")

    def denied_resources(self):
        # The catalog too: allowed dataset:* on it, the principal could run
        # unchecked SQL (QueryUnchecked), which the cases below refuse.
        return [*self._namespace("hr"), "abi:-:-:dataset:catalog/-"]

    def read_only_resources(self):
        return self._namespace("frozen")

    def outcome_of(self, exc):
        if isinstance(exc, DatasetNotFoundError):
            return NOT_FOUND
        if isinstance(exc, ValueError):
            return INVALID
        return None

    def cases(self):
        join = (
            "SELECT count(*) AS n FROM orders o JOIN (SELECT * FROM items) i USING (id)"
        )
        reaching = "WITH x AS (SELECT * FROM hr.salaries) SELECT count(*) AS n FROM x"
        return [
            Case(
                "list datasets",
                lambda d: d.list(),
                nobody=ok([]),
                granted=ok([("sales", "items"), ("sales", "orders")]),
                denied=ok([("frozen", "f"), ("sales", "items"), ("sales", "orders")]),
                view=lambda infos: sorted((i.namespace, i.name) for i in infos),
            ),
            Case(
                "describe a denied dataset",
                lambda d: d.describe("salaries", namespace="hr"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "query granted datasets through a join and a subquery",
                lambda d: d.query(join, namespace="sales"),
                nobody=HIDDEN,
                granted=ok([2]),
                denied=ok([2]),
                view=_rows,
            ),
            Case(
                "stream the same query",
                lambda d: _streamed(d, join, "sales"),
                nobody=HIDDEN,
                granted=ok([2]),
                denied=ok([2]),
            ),
            Case(
                "reach a denied dataset through a CTE",
                lambda d: d.query(reaching, namespace="sales"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "a CTE elsewhere does not hide a denied dataset",
                lambda d: d.query(
                    "SELECT count(*) AS n FROM salaries WHERE EXISTS "
                    "(WITH salaries AS (SELECT 1) SELECT * FROM salaries)",
                    namespace="hr",
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "a denied dataset named in another case",
                lambda d: d.query(
                    "SELECT count(*) AS n FROM HR.SALARIES", namespace="sales"
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "a granted dataset named in another case",
                lambda d: d.query(
                    "SELECT count(*) AS n FROM ORDERS", namespace="sales"
                ),
                nobody=HIDDEN,
                granted=ok([2]),
                denied=ok([2]),
                view=_rows,
            ),
            Case(
                "a name DuckDB resolves that is not a dataset",
                lambda d: d.query(
                    "SELECT count(*) AS n FROM duckdb_tables", namespace="sales"
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "a denied dataset in a recursive CTE's anchor",
                lambda d: d.query(
                    "WITH RECURSIVE salaries AS (SELECT * FROM salaries "
                    "UNION ALL SELECT * FROM salaries WHERE false) "
                    "SELECT count(*) AS n FROM salaries",
                    namespace="hr",
                ),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "a CTE named as no dataset can be",
                lambda d: d.query(
                    'WITH "a-b" AS (SELECT 1 AS n) SELECT * FROM "a-b"',
                    namespace="sales",
                ),
                nobody=ok([1]),
                granted=ok([1]),
                denied=ok([1]),
                view=_rows,
            ),
            Case(
                "read a file as a table",
                lambda d: d.query("SELECT * FROM '/etc/passwd'", namespace="sales"),
                nobody=REFUSED_QUERY,
                granted=REFUSED_QUERY,
                denied=REFUSED_QUERY,
            ),
            Case(
                "read a host file as text",
                lambda d: d.query(
                    "SELECT * FROM read_text('/proc/self/environ')",
                    namespace="sales",
                ),
                nobody=REFUSED_QUERY,
                granted=REFUSED_QUERY,
                denied=REFUSED_QUERY,
            ),
            Case(
                "read a file through a table function",
                lambda d: d.query("SELECT * FROM read_csv('/etc/passwd')"),
                nobody=REFUSED_QUERY,
                granted=REFUSED_QUERY,
                denied=REFUSED_QUERY,
            ),
            Case(
                "write to a read-only dataset",
                lambda d: d.write("f", [{"id": 3}], namespace="frozen"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "drop a denied dataset",
                lambda d: d.drop("salaries", namespace="hr"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "namespace version of a denied namespace",
                lambda d: d.namespace_version("hr"),
                nobody=ok(None),
                granted=ok(None),
                denied=ok(None),
            ),
            Case(
                "create a dataset in a granted namespace",
                lambda d: d.create(_spec("sales", "returns")),
                nobody=HIDDEN,
                granted=ANY_OK,
                denied=ANY_OK,
            ),
        ]


def _as_nexus_user(iam):
    """A Nexus call: api on behalf of a user who holds ``dataset:*`` on every
    dataset (a custom policy: the built-in roles reach a workspace's datasets)."""
    from naas_abi_core.engine.call_context import (
        CallContext,
        as_service_account,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
    from naas_abi_core.services.iam.tests.iam_harness import document, statement

    with as_service_account("engine"):
        record = iam.ensure_user(LEGACY_NEXUS_ISSUER, "nexus-1")
        policy = iam.create_policy(
            "every-dataset",
            document(
                statement("Allow", ["dataset:*"], ["abi:*:*:dataset:dataset/*"]),
                statement("Allow", ["dataset:*"], ["abi:*:*:dataset:namespace/*"]),
            ),
        )
        iam.attach_policy(policy.id, record.id)

    return use_call_context(
        CallContext(principal=service_account("api"), on_behalf_of=user("nexus-1"))
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_text('/proc/self/environ')",
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM '/etc/passwd'",
        "SELECT * FROM duckdb_tables()",
        "DESCRIBE orders",
        "SELECT 1; SELECT 2",
    ],
)
def test_a_caller_allowed_every_dataset_is_still_held_to_dataset_sql(tmp_path, sql):
    """Allowed every dataset skips the per-dataset checks, not the SQL rules:
    a file read reads no dataset."""
    owner, iam = TestDatasetAuthorization()._owner(tmp_path)
    with _as_nexus_user(iam), pytest.raises(ValueError):
        owner.query(sql, namespace="sales")


def test_a_caller_allowed_every_dataset_reads_them_all(tmp_path):
    owner, iam = TestDatasetAuthorization()._owner(tmp_path)
    with _as_nexus_user(iam):
        result = owner.query(
            "SELECT count(*) AS n FROM orders JOIN hr.salaries USING (id)",
            namespace="sales",
        )
        assert _rows(result) == [2]
        with pytest.raises(DatasetNotFoundError):
            owner.query("SELECT * FROM duckdb_tables", namespace="sales")


def test_the_engine_maintains_the_catalog_with_unchecked_sql(tmp_path):
    from naas_abi_core.services.iam.enforcement import internal_call

    owner, _ = TestDatasetAuthorization()._owner(tmp_path)
    with internal_call():
        described = owner.query("DESCRIBE orders", namespace="sales")
    assert "id" in {str(row.get("column_name")) for row in described.rows}
