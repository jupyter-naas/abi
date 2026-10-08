import asyncio
import csv
import io

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.dataset_resources import (
    DatasetResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetPort import ColumnSpec, DatasetSpec, PartitionSpec

NAMESPACE = "seed"


def table_csv(text: str) -> bytes:
    return f"value\n{text}\n".encode()


def _rows(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if not line.startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


@pytest.fixture
def service(tmp_path):
    service = DatasetFactory.DatasetServiceDuckLake(
        catalog=f"sqlite:{tmp_path / 'datasets.sqlite'}",
        data_path=str(tmp_path / "datasets"),
        retry_base_delay_seconds=0.01,
    )
    for name, value in fixtures.SEED_ITEMS.items():
        service.create(
            DatasetSpec(
                name=name, namespace=NAMESPACE, columns=(ColumnSpec(name="value", type="string"),)
            )
        )
        service.write(name, [{"value": value.decode()}], namespace=NAMESPACE)
    return service


@pytest.fixture
def commits(service):
    service.create(
        DatasetSpec(
            name="commits",
            namespace="acme",
            columns=(
                ColumnSpec(name="sha", type="string"),
                ColumnSpec(name="day", type="date"),
                ColumnSpec(name="additions", type="integer"),
                ColumnSpec(name="ratio", type="double"),
                ColumnSpec(name="merged", type="boolean"),
                ColumnSpec(name="meta", type="json"),
            ),
            partitions=(PartitionSpec(column="day", transform="month"),),
            primary_key=("sha",),
        )
    )
    service.write(
        "commits",
        [
            {
                "sha": "a",
                "day": "2026-10-01",
                "additions": 3,
                "ratio": 0.5,
                "merged": True,
                "meta": {"k": 1},
            },
            {
                "sha": "b",
                "day": "2026-10-02",
                "additions": 5,
                "ratio": None,
                "merged": False,
                "meta": None,
            },
        ],
        namespace="acme",
    )
    return service


class TestDatasetResourcesOnDuckLake(ServiceResourcesContract):
    base = NAMESPACE
    sized = False

    @pytest.fixture
    def resources(self, service):
        return DatasetResources(service)

    def encode(self, text: str) -> bytes:
        return table_csv(text)

    def assert_shown(self, shown, text):
        assert shown is not None and [r["value"] for r in _rows(shown)] == [text]

    def assert_downloaded(self, data, text):
        assert [r["value"] for r in _rows(data.decode())] == [text]


def run(coro):
    return asyncio.run(coro)


def test_root_lists_namespaces_and_namespaces_list_tables(commits):
    resources = DatasetResources(commits)

    root = run(resources.list())
    acme = run(resources.list("acme"))

    assert [(e.id, e.kind) for e in root.entries] == [("acme", "container"), ("seed", "container")]
    assert [(e.id, e.name, e.kind) for e in acme.entries] == [("acme/commits", "commits", "item")]
    assert run(resources.stat("acme")).kind == "container"
    with pytest.raises(ResourceNotFound):
        run(resources.list("nowhere"))


def test_read_shows_schema_row_count_and_rows(commits):
    detail = run(DatasetResources(commits).read("acme/commits"))
    text = detail.content.text

    assert detail.entry.attributes["rows"] == "2"
    assert detail.entry.attributes["media_type"] == "text/csv"
    assert (
        "# columns: sha string, day date, additions integer, ratio double, merged boolean, meta json"
        in text
    )
    assert "# partitions: day month" in text
    assert "# primary key: sha" in text
    rows = sorted(_rows(text), key=lambda r: r["sha"])
    assert rows[0] == {
        "sha": "a",
        "day": "2026-10-01",
        "additions": "3",
        "ratio": "0.5",
        "merged": "true",
        "meta": '{"k": 1}',
    }
    assert rows[1]["ratio"] == "" and rows[1]["merged"] == "false" and rows[1]["meta"] == ""


def test_previews_are_bounded_by_rows(service):
    service.write("alpha", [{"value": f"row {i}"} for i in range(9)], namespace=NAMESPACE)

    detail = run(DatasetResources(service, preview_rows=3).read("seed/alpha"))

    assert detail.content.truncated is True
    assert len(_rows(detail.content.text)) == 3
    assert detail.entry.attributes["rows"] == "10"


def test_replacing_coerces_cells_to_column_types(commits):
    resources = DatasetResources(commits)

    run(
        resources.write(
            "acme/commits",
            b"# comment lines from a preview are skipped\n"
            b"sha,day,additions,ratio,merged,meta\n"
            b'c,2026-10-03,7,1.25,yes,"{""x"": [1, 2]}"\n'
            b"d,2026-10-04,,,,\n",
        )
    )

    result = commits.query("SELECT * FROM commits ORDER BY sha", namespace="acme")
    assert [r["sha"] for r in result.rows] == ["c", "d"]
    first = result.rows[0]
    assert (first["additions"], first["ratio"], first["merged"], first["meta"]) == (
        7,
        1.25,
        True,
        {"x": [1, 2]},
    )
    assert result.rows[1]["additions"] is None


@pytest.mark.parametrize(
    "body",
    [
        b"sha,unknown\nx,1\n",  # unknown column
        b"sha,additions\nx,many\n",  # not an integer
        b"sha,merged\nx,perhaps\n",  # not a boolean
        b"sha,meta\nx,{not json\n",  # invalid JSON
        b"",  # no header
    ],
)
def test_invalid_rows_are_rejected_and_the_table_is_kept(commits, body):
    resources = DatasetResources(commits)

    with pytest.raises(InvalidResource):
        run(resources.write("acme/commits", body))

    assert run(resources.stat("acme/commits")).attributes["rows"] == "2"


def test_creating_a_table_from_csv_uses_string_columns(service):
    resources = DatasetResources(service)

    created = run(resources.write("fresh/people", b"name,city\nAda,London\nAlan,Wilmslow\n"))

    assert (created.id, created.kind, created.attributes["rows"]) == ("fresh/people", "item", "2")
    info = service.describe("people", namespace="fresh")
    assert [(c.name, c.type) for c in info.columns] == [("name", "string"), ("city", "string")]


@pytest.mark.parametrize("bad", ["fresh/bad-name", "bad ns/table", "fresh", "a/b/c", "fresh/1st"])
def test_ids_must_be_namespace_and_table_identifiers(service, bad):
    with pytest.raises(InvalidResource):
        run(DatasetResources(service).write(bad, b"value\nx\n"))


def test_new_tables_need_identifier_columns(service):
    with pytest.raises(InvalidResource):
        run(DatasetResources(service).write("fresh/t", b"bad column\nx\n"))


def test_download_exports_every_row(service):
    service.write("alpha", [{"value": f"row {i}"} for i in range(30)], namespace=NAMESPACE)

    data = run(DatasetResources(service, preview_rows=2).download("seed/alpha", max_bytes=1 << 20))

    assert len(_rows(data.decode())) == 31


def test_a_new_table_whose_rows_fail_is_not_left_behind(service):
    class FailingWrites:
        def __getattr__(self, name):
            return getattr(service, name)

        def write(self, *args, **kwargs):
            raise ValueError("storage refused the rows")

    with pytest.raises(InvalidResource):
        run(DatasetResources(FailingWrites()).write("fresh/people", b"name\nAda\n"))

    assert [i.name for i in service.list(namespace="fresh")] == []


# --- listing attributes, search and the structured preview ---------------------------


class CountingDatasets:
    """The real service, counting queries (row counts cost one query per page)."""

    def __init__(self, inner, *, fail_queries: bool = False) -> None:
        self.inner = inner
        self.queries: list[str] = []
        self.fail_queries = fail_queries

    def query(self, sql, **kwargs):
        self.queries.append(sql)
        if self.fail_queries:
            raise RuntimeError("catalog busy")
        return self.inner.query(sql, **kwargs)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_namespaces_carry_their_tables(commits):
    root = {e.id: e for e in run(DatasetResources(commits).list()).entries}

    assert root["acme"].attributes["tables"] == "1"
    assert root["acme"].attributes["summary"] == "commits"
    assert root["seed"].attributes["tables"] == "3"
    assert root["seed"].attributes["summary"] == "alpha, beta, gamma"


def test_tables_carry_schema_facts_and_counts_in_one_query(commits):
    datasets = CountingDatasets(commits)
    commits.write("alpha", [{"value": "more"}], namespace=NAMESPACE)

    acme = run(DatasetResources(datasets).list("acme")).entries[0]
    seed = {e.name: e for e in run(DatasetResources(datasets).list(NAMESPACE)).entries}

    assert acme.attributes == {
        "columns": "6",
        "primary_key": "sha",
        "partitions": "day (month)",
        "rows": "2",
        "summary": "sha, day, additions, ratio, merged, meta",
    }
    assert seed["alpha"].attributes["rows"] == "2" and seed["beta"].attributes["rows"] == "1"
    assert len(datasets.queries) == 2  # one per listed page
    assert "UNION ALL" in datasets.queries[1]


def test_tables_list_without_counts_when_queries_fail(commits):
    entry = run(
        DatasetResources(CountingDatasets(commits, fail_queries=True)).list("acme")
    ).entries[0]

    assert entry.attributes["columns"] == "6"
    assert "rows" not in entry.attributes


def test_search_filters_names_at_each_level(commits):
    resources = DatasetResources(commits)

    assert resources.capabilities.search is True
    assert [e.id for e in run(resources.list(query="SE")).entries] == ["seed"]
    assert [e.name for e in run(resources.list(NAMESPACE, query="ph")).entries] == ["alpha"]


def test_read_carries_a_typed_table_view(commits):
    view = run(DatasetResources(commits).read("acme/commits")).view

    assert view["type"] == "table"
    assert view["columns"] == [
        {"name": "sha", "type": "string"},
        {"name": "day", "type": "date"},
        {"name": "additions", "type": "integer"},
        {"name": "ratio", "type": "double"},
        {"name": "merged", "type": "boolean"},
        {"name": "meta", "type": "json"},
    ]
    assert view["total"] == 2
    assert view["primary_key"] == ["sha"]
    assert view["partitions"] == [{"column": "day", "transform": "month"}]
    rows = sorted(view["rows"], key=lambda r: r[0])
    assert rows[0] == ["a", "2026-10-01", 3, 0.5, True, {"k": 1}]
    assert rows[1][3] is None and rows[1][5] is None


def test_the_write_format_says_rows_are_replaced(service):
    assert "replaces every row" in DatasetResources(service).capabilities.write_format
