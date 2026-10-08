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

from naas_abi_core.services.dataset.DatasetPort import DatasetNotFoundError
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
    """The snapshot of the people table in *namespace*; None if never written."""
    try:
        return service.describe(
            config["data"]["tables"]["people"], namespace=namespace
        ).snapshot_id
    except DatasetNotFoundError:
        return None
    except Exception:  # noqa: BLE001 - an unknown namespace fails in adapter terms
        return None


def _read_namespace(
    service: DatasetService, config: dict[str, Any], namespace: str
) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for logical, table in config["data"]["tables"].items():
        tables[logical] = ds.query(
            service, f"SELECT * FROM {table}", namespace=namespace, table=table
        )
    return tables


def load_store(
    service: DatasetService, config: dict[str, Any], namespaces: list[str]
) -> MemoryPeopleStore:
    """One store over the datasets in *namespaces*, in that order.

    A person found in two of them is kept from the first, with that dataset's
    sections only, so a profile never mixes two sources. A namespace that was
    never written is skipped; if none was, the error names the sync job.
    """
    merged: dict[str, list[dict[str, Any]]] = {
        logical: [] for logical in config["data"]["tables"]
    }
    seen: set[str] = set()
    found = False
    for namespace in namespaces:
        if dataset_version(service, config, namespace) is None:
            continue
        found = True
        tables = _read_namespace(service, config, namespace)
        own = {row["slug"] for row in tables.get("people", [])} - seen
        for logical, rows in tables.items():
            merged[logical].extend(row for row in rows if row.get("slug") in own)
        seen |= own
    if not found:
        people = config["data"]["tables"]["people"]
        raise ds.DatasetsMissingError(
            people,
            namespaces[0] if namespaces else config["data"]["namespace"],
            command=SYNC_COMMAND,
        )
    return MemoryPeopleStore(merged, config)
