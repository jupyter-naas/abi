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
