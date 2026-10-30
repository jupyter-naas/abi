"""One materialized dataset per people graph: the read model of ``workspace_dataset``.

    named graph (source of truth)  ->  build_rows + gate  ->  <namespace>__<graph>

A sync job writes a graph, then calls ``materialize_graph`` for it. The app
never runs ``build_rows`` on a request: it loads the datasets of the graphs the
workspace may read (``load_store``), which is a few table scans, and caches the
result until one of those datasets gets a new snapshot.

Which graphs a workspace may read is Nexus's answer, not this module's. This
only maps a graph IRI to the namespace its rows live in.
"""

from __future__ import annotations

import re
from typing import Any

from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    datasets as ds,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    export_people_from_graph as export,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    triple_store_graph as tg,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.memory_people_store import (
    MemoryPeopleStore,
)
from rdflib import Graph

GRAPH_MARKER = "/graph/"
# What builds a workspace's people: shown after "Run:" when they are missing.
SYNC_COMMAND = (
    "people_intelligence_sync_workspace_people_job (Dagster), which writes the "
    "workspace people graph and its dataset"
)


def graph_namespace(config: dict[str, Any], iri: str) -> str:
    """The dataset namespace holding the rows of named graph *iri*.

    ``http://ontology.naas.ai/graph/ws-1fe2cd925ef1/people`` under namespace
    ``people_fmz`` is ``people_fmz__ws_1fe2cd925ef1_people``.
    """
    tail = iri.split(GRAPH_MARKER, 1)[1] if GRAPH_MARKER in iri else iri
    slug = re.sub(r"[^A-Za-z0-9]+", "_", tail).strip("_").lower()
    if not slug:
        raise ValueError(f"Cannot name a dataset namespace after graph {iri!r}")
    return f"{config['data']['namespace']}__{slug}"


def _for_namespace(config: dict[str, Any], namespace: str) -> dict[str, Any]:
    return {**config, "data": {**config["data"], "namespace": namespace}}


def materialize_graph(
    service: DatasetService, config: dict[str, Any], iri: str, graph: Graph
) -> dict[str, Any]:
    """Replace the dataset of *iri* with the people in *graph*.

    An empty graph writes empty tables, so "synced, nobody on the slides" reads
    as an empty directory rather than as a missing export.
    """
    namespace = graph_namespace(config, iri)
    tables = export.build_rows(graph, config)
    export.publish(service, _for_namespace(config, namespace), tables)
    return {
        "graph": iri,
        "namespace": namespace,
        "people": len(tables["people"]),
    }


def materialize_from_triple_store(
    triple_store: Any, service: DatasetService, config: dict[str, Any], iri: str
) -> dict[str, Any]:
    """``materialize_graph`` for a graph read back from the triple store."""
    try:
        graph = tg.read_named_graph(triple_store, iri)
    except tg.GraphNotFoundError:
        graph = Graph()
    return materialize_graph(service, config, iri, graph)


def dataset_version(
    service: DatasetService, config: dict[str, Any], namespace: str
) -> int | None:
    """The last snapshot that changed *namespace*; None if never written.

    Per namespace on purpose: the catalog's current snapshot moves on every
    write anywhere, and keying the app's cache on it would drop every
    workspace's people whenever one workspace syncs.
    """
    del config
    return service.namespace_version(namespace)


def _written_tables(service: DatasetService, namespace: str) -> set[str] | None:
    """The tables *namespace* holds, or None if the service cannot say."""
    try:
        return {info.name for info in service.list(namespace=namespace)}
    except Exception:  # noqa: BLE001
        return None


def read_namespace(
    service: DatasetService, config: dict[str, Any], namespace: str
) -> dict[str, list[dict[str, Any]]] | None:
    """Every table of *namespace*, or None if it was never written."""
    if dataset_version(service, config, namespace) is None:
        return None
    tables: dict[str, list[dict[str, Any]]] = {}
    written = _written_tables(service, namespace)
    for logical, table in config["data"]["tables"].items():
        if written is not None and table not in written and logical != "people":
            # Written before this table existed (connections): read as empty,
            # without a failing query the adapter would log as an error.
            tables[logical] = []
            continue
        try:
            tables[logical] = ds.query(
                service, f"SELECT * FROM {table}", namespace=namespace, table=table
            )
        except ds.DatasetsMissingError:
            # A sync that stopped halfway leaves a section table unwritten:
            # list the people without it rather than not at all.
            if logical == "people":
                raise
            tables[logical] = []
    return tables


# People columns a later source may fill when the first left them empty.
FILLED_COLUMNS = ("linkedin_url",)


def merge_tables(
    config: dict[str, Any], sources: list[dict[str, list[dict[str, Any]]]]
) -> MemoryPeopleStore:
    """One store over *sources*, in that order.

    A person found in two of them is kept from the first, with that source's
    sections only, so a profile never mixes two sources. Shared tables
    (``ds.SHARED_TABLES``: connections) are the exception: each source states
    its own, so they are united, one row per key, the first source's kept.

    A person's LinkedIn URL is the other exception: kept from the first source
    that states it (``FILLED_COLUMNS``). A people graph that never knew it
    (a curated directory) still gets it from the person's own LinkedIn import.
    """
    merged: dict[str, list[dict[str, Any]]] = {
        logical: [] for logical in config["data"]["tables"]
    }
    seen: set[str] = set()
    shared_keys: dict[str, set[tuple[Any, ...]]] = {
        logical: set() for logical in ds.SHARED_TABLES
    }
    kept: dict[str, dict[str, Any]] = {}
    for tables in sources:
        own = {row["slug"] for row in tables.get("people", [])} - seen
        for row in tables.get("people", []):
            first = kept.get(row["slug"])
            if first is None:
                continue
            for column in FILLED_COLUMNS:
                if not first.get(column) and row.get(column):
                    first[column] = row[column]
        for logical, rows in tables.items():
            if logical not in merged:
                continue
            if logical in ds.SHARED_TABLES:
                key_columns = ds.SHARED_TABLES[logical]
                for row in rows:
                    key = tuple(row.get(column) for column in key_columns)
                    if key not in shared_keys[logical]:
                        shared_keys[logical].add(key)
                        merged[logical].append(row)
                continue
            taken = [
                dict(row) if logical == "people" else row
                for row in rows
                if row.get("slug") in own
            ]
            merged[logical].extend(taken)
            if logical == "people":
                kept.update((row["slug"], row) for row in taken)
        seen |= own
    return MemoryPeopleStore(merged, config)


def missing_error(
    config: dict[str, Any], namespaces: list[str]
) -> ds.DatasetsMissingError:
    """No dataset of *namespaces* was ever written: name the job that writes them."""
    return ds.DatasetsMissingError(
        config["data"]["tables"]["people"],
        namespaces[0] if namespaces else config["data"]["namespace"],
        command=SYNC_COMMAND,
    )


def load_store(
    service: DatasetService, config: dict[str, Any], namespaces: list[str]
) -> MemoryPeopleStore:
    """One store over the datasets in *namespaces*, in that order.

    A namespace that was never written is skipped; if none was, the error
    names the sync job.
    """
    sources = [
        tables
        for tables in (read_namespace(service, config, ns) for ns in namespaces)
        if tables is not None
    ]
    if not sources:
        raise missing_error(config, namespaces)
    return merge_tables(config, sources)
