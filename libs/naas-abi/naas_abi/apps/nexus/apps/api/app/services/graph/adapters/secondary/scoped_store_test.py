"""Regressions for workspace query validation on a cold API process."""

import subprocess
import sys
from pathlib import Path

from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary import (
    scoped_store,
)


def test_concurrent_cold_composer_queries_keep_parser_valid():
    # An already-used parser hides the defect. A separate process reproduces the
    # first simultaneous column/page/count requests after an API restart.
    script = r"""
import runpy
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from naas_abi.apps.nexus.apps.api.app.services.graph.query.column_discovery import discover_columns
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import GraphAccessError, GraphQuerySpecError

query_shape = runpy.run_path(sys.argv[1])["query_shape"]
queries = []
class Capture:
    def select(self, query):
        queries.append(query)
        return []

discover_columns(
    Capture(),
    graph_uris=["http://example.org/graphs/market"],
    class_uris=["http://example.org/Organization"],
)
queries.extend([
    "SELECT ?s ?label WHERE { GRAPH <http://example.org/graphs/market> { "
    "?s a <http://example.org/Organization> . OPTIONAL { "
    "?s <http://www.w3.org/2000/01/rdf-schema#label> ?label } } } LIMIT 50",
    "SELECT (COUNT(DISTINCT ?s) AS ?count) WHERE { "
    "GRAPH <http://example.org/graphs/market> { ?s a <http://example.org/Organization> } }",
])
start = Barrier(len(queries))
sys.setswitchinterval(0.0001)
def validate(query):
    start.wait(timeout=10)
    kind, offset = query_shape(query)
    assert kind == "SelectQuery"
    assert query[offset:offset + 5] == "WHERE"

with ThreadPoolExecutor(max_workers=len(queries)) as pool:
    list(pool.map(validate, queries))
# Subsequent requests must still validate after the initial burst.
for query in queries:
    query_shape(query + "\n# retry")
# Parsing remains a security boundary; the lock must not bypass validation.
for query, expected in [
    ("SELECT ?s FROM <urn:private> WHERE { ?s ?p ?o }", GraphAccessError),
    ("SELECT ?s WHERE { SERVICE <https://example.org/sparql> { ?s ?p ?o } }", GraphAccessError),
    ("not SPARQL", GraphQuerySpecError),
]:
    try:
        query_shape(query)
    except expected:
        pass
    else:
        raise AssertionError("Query validation was bypassed")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(Path(scoped_store.__file__).resolve())],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_workspace_store_limits_dataset_to_values_graph_clause():
    from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
        WorkspaceGraphStore,
    )

    g1 = "http://ontology.example/graph/a"
    g2 = "http://ontology.example/graph/b"
    scope = GraphAccessScope.resolve(
        "ws-1",
        __import__(
            "naas_abi.apps.nexus.graph_policy_config",
            fromlist=["WorkspaceGraphPolicyConfig"],
        ).WorkspaceGraphPolicyConfig(read_all=True),
        owned=set(),
        role="owner",
        catalog={g1, g2},
    )

    class CaptureStore:
        def __init__(self):
            self.queries: list[str] = []

        def list_graphs(self):
            return [g1, g2]

        def query(self, query: str):
            self.queries.append(query)
            from rdflib.query import Result

            result = Result("SELECT")
            result.vars = []
            result.bindings = []
            return result

    inner = CaptureStore()
    store = WorkspaceGraphStore(inner, scope)
    store.query(
        "PREFIX x: <http://example/> SELECT ?c WHERE { "
        f"VALUES ?g {{ <{g1}> }} GRAPH ?g {{ ?s ?p ?o }} }}"
    )
    assert len(inner.queries) == 1
    sent = inner.queries[0]
    assert f"FROM <{g1}>" in sent
    assert f"FROM NAMED <{g1}>" in sent
    assert g2 not in sent


def test_workspace_store_unions_values_graph_clauses_for_cross_graph_queries():
    from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope
    from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
        WorkspaceGraphStore,
    )

    g1 = "http://ontology.example/graph/data"
    g2 = "http://ontology.example/graph/links"
    scope = GraphAccessScope.resolve(
        "ws-1",
        __import__(
            "naas_abi.apps.nexus.graph_policy_config",
            fromlist=["WorkspaceGraphPolicyConfig"],
        ).WorkspaceGraphPolicyConfig(read_all=True),
        owned=set(),
        role="owner",
        catalog={g1, g2},
    )

    class CaptureStore:
        def __init__(self):
            self.queries: list[str] = []

        def list_graphs(self):
            return [g1, g2]

        def query(self, query: str):
            self.queries.append(query)
            from rdflib.query import Result

            result = Result("SELECT")
            result.vars = []
            result.bindings = []
            return result

    inner = CaptureStore()
    store = WorkspaceGraphStore(inner, scope)
    store.query(
        "SELECT ?p WHERE { "
        f"VALUES ?g {{ <{g1}> }} VALUES ?rg {{ <{g1}> <{g2}> }} "
        "GRAPH ?g { ?s a <http://example/Person> } "
        "GRAPH ?rg { ?s ?p ?o } }"
    )
    sent = inner.queries[0]
    assert f"FROM <{g1}>" in sent
    assert f"FROM <{g2}>" in sent
