"""Dataset definitions and access for the People Search app.

One profile is nine tables rather than one nested document, because the dataset
service is tabular and typed: a wrong column fails at write time instead of
rendering as a blank section. ``profile_payload`` puts a person back together
for the profile page; ``search_payload`` queries across the tables for results.

Photographs are not in here. ``people.photo_url`` is an address; the image
itself belongs in object storage or on the site it is published from.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetAlreadyExistsError,
    DatasetNotFoundError,
    DatasetSpec,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService

# Logical name -> (primary key, columns). The logical name is what config.yaml
# maps to a physical table, so a client can serve their own tables from the
# same app without touching this file.
TABLES: dict[str, tuple[tuple[str, ...], tuple[tuple[str, str], ...]]] = {
    "people": (
        ("slug",),
        (
            ("slug", "string"),
            ("full_name", "string"),
            ("headline", "string"),
            ("about", "string"),
            ("quote", "string"),
            ("photo_url", "string"),
            ("organization", "string"),
            ("office", "string"),
            ("city", "string"),
            ("country", "string"),
            ("country_code", "string"),
            ("service_line", "string"),
            ("grade", "string"),
            ("years_of_experience", "integer"),
            ("public_profile_url", "string"),
            # Contact details. Empty unless the instance publishes them
            # (privacy.publish_contact_details), and never in search_text.
            ("email", "string"),
            ("phone", "string"),
            ("linkedin_url", "string"),
            # Accent-folded, lowercased concatenation of the searchable fields,
            # built at export time so matching is a SQL LIKE instead of shipping
            # the whole directory to the browser.
            ("search_text", "string"),
        ),
    ),
    "experience": (
        ("slug", "seq"),
        (
            ("slug", "string"),
            ("seq", "integer"),
            # Rows of one employer share a group_seq, so the profile can show
            # several roles under one organization the way a CV does.
            ("group_seq", "integer"),
            ("organization", "string"),
            ("location", "string"),
            ("title", "string"),
            ("description", "string"),
            ("start_date", "date"),
            ("end_date", "date"),
            ("duration_label", "string"),
        ),
    ),
    "education": (
        ("slug", "seq"),
        (
            ("slug", "string"),
            ("seq", "integer"),
            ("school", "string"),
            ("degree", "string"),
            ("field_of_study", "string"),
            ("description", "string"),
            ("start_date", "date"),
            ("end_date", "date"),
        ),
    ),
    "skills": (
        ("slug", "skill_name"),
        (
            ("slug", "string"),
            ("skill_name", "string"),
        ),
    ),
    "certifications": (
        ("slug", "seq"),
        (
            ("slug", "string"),
            ("seq", "integer"),
            ("name", "string"),
            ("issuer", "string"),
            ("issued", "date"),
            ("expires", "date"),
            ("status", "string"),
            ("credential_url", "string"),
        ),
    ),
    "languages": (
        ("slug", "seq"),
        (
            ("slug", "string"),
            ("seq", "integer"),
            ("name", "string"),
            ("proficiency", "string"),
        ),
    ),
    "recommendations": (
        ("slug", "seq"),
        (
            ("slug", "string"),
            ("seq", "integer"),
            ("author_name", "string"),
            ("author_headline", "string"),
            ("relationship", "string"),
            ("written_on", "date"),
            ("content", "string"),
        ),
    ),
    "interests": (
        ("slug", "seq"),
        (
            ("slug", "string"),
            ("seq", "integer"),
            ("name", "string"),
            ("description", "string"),
            ("kind", "string"),
        ),
    ),
    "sources": (
        ("slug", "seq"),
        (
            ("slug", "string"),
            ("seq", "integer"),
            ("source_url", "string"),
            ("source_label", "string"),
        ),
    ),
}


class DatasetsMissingError(RuntimeError):
    """The app's tables have not been exported yet.

    Carries the command that builds them, so the API can say that instead of
    answering an empty list as though nobody worked here.
    """

    BUILD_COMMAND = (
        "cd libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel "
        "&& make people-datasets"
    )

    def __init__(self, table: str, namespace: str) -> None:
        self.table = table
        self.namespace = namespace
        super().__init__(
            f"Dataset not exported: {namespace}.{table}\nRun: {self.BUILD_COMMAND}"
        )

    def as_detail(self) -> dict[str, str]:
        return {
            "error": "missing_dataset",
            "dataset": f"{self.namespace}.{self.table}",
            "command": self.BUILD_COMMAND,
            "message": str(self),
        }


def dataset_spec(logical_name: str, *, table: str, namespace: str) -> DatasetSpec:
    """The typed schema of one table, named as the configuration asks."""
    try:
        primary_key, columns = TABLES[logical_name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown table {logical_name!r}. Known: {', '.join(sorted(TABLES))}"
        ) from exc
    return DatasetSpec(
        name=table,
        namespace=namespace,
        columns=tuple(ColumnSpec(name=name, type=type_) for name, type_ in columns),
        primary_key=primary_key,
    )


def ensure_dataset(service: DatasetService, spec: DatasetSpec) -> None:
    """Create the table if it is not there; leave it alone if it is.

    A rebuild replaces rows rather than the table, so the catalog keeps the
    snapshot history that makes a bad export recoverable. The exception is a
    table whose columns no longer match the spec: the port cannot alter a
    table, so it is dropped and recreated, and its history goes with it.
    """
    try:
        service.create(spec)
    except DatasetAlreadyExistsError:
        existing = service.describe(spec.name, namespace=spec.namespace)
        if [c.name for c in existing.columns] == [c.name for c in spec.columns]:
            return
        service.drop(spec.name, namespace=spec.namespace)
        service.create(spec)


def replace_rows(
    service: DatasetService, spec: DatasetSpec, rows: list[dict[str, Any]]
) -> None:
    """Write one table's rows, then materialize them.

    Without the flush, a batch under the inlining limit stays in the catalog
    database and no Parquet is written, which makes the export look like it
    produced nothing.
    """
    ensure_dataset(service, spec)
    service.write(spec.name, rows, namespace=spec.namespace, mode="replace")
    service.flush(spec.name, namespace=spec.namespace)


def query(
    service: DatasetService, sql: str, *, namespace: str, table: str
) -> list[dict[str, Any]]:
    """Run one read, translating 'never exported' into something actionable."""
    try:
        return service.query(sql, namespace=namespace).rows
    except DatasetNotFoundError as exc:
        raise DatasetsMissingError(table, namespace) from exc
    except Exception as exc:
        # A namespace that was never written fails in the adapter's own
        # vocabulary rather than the port's, so ask the port whether the table
        # exists before claiming this is a missing export. Anything else is a
        # real error and is left alone.
        try:
            service.describe(table, namespace=namespace)
        except DatasetNotFoundError:
            raise DatasetsMissingError(table, namespace) from exc
        raise


def sql_literal(value: str) -> str:
    """Quote a string for inline SQL by doubling single quotes.

    Only ever used for values this app has already constrained: folded search
    words, a slug that matched its pattern, a facet value read back from the
    people table.
    """
    return "'" + str(value).replace("'", "''") + "'"


def slug_list(slugs: list[str]) -> str:
    return ", ".join(sql_literal(slug) for slug in slugs)


def fetch_people(
    service: DatasetService,
    *,
    namespace: str,
    table: str,
    where: str = "",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    clause = f" WHERE {where}" if where else ""
    bound = f" LIMIT {int(limit)}" if limit else ""
    sql = f"SELECT * FROM {table}{clause} ORDER BY full_name{bound}"
    return query(service, sql, namespace=namespace, table=table)


def fetch_children(
    service: DatasetService,
    *,
    namespace: str,
    table: str,
    slugs: list[str],
    order_by: str = "seq",
) -> dict[str, list[dict[str, Any]]]:
    """Rows of one child table, grouped by person.

    A person with no rows is absent from the result rather than present with an
    empty list: the caller decides what "nothing recorded" looks like.
    """
    if not slugs:
        return {}
    sql = (
        f"SELECT * FROM {table} WHERE slug IN ({slug_list(slugs)}) "
        f"ORDER BY slug, {order_by}"
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in query(service, sql, namespace=namespace, table=table):
        grouped.setdefault(row["slug"], []).append(row)
    return grouped
