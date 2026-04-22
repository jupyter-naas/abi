"""Apache Jena Fuseki (TDB2) triple store adapter.

This adapter implements :class:`ITripleStorePort` over HTTP for a Fuseki dataset
backed by Jena TDB2.

How it works
------------
- A single base dataset URL is configured (for example
  ``http://localhost:3030/ds``).
- The adapter derives standard Fuseki endpoints:
  - ``<dataset>/query`` for SPARQL query operations
  - ``<dataset>/update`` for SPARQL update operations
  - ``<dataset>/data`` reserved for graph-store operations
- At initialization, a lightweight ``ASK`` query is sent to verify connectivity.

Transactions and consistency
----------------------------
Jena TDB2 provides ACID transactions on the server side. This adapter relies on
that behavior by submitting each write request as a *single SPARQL Update
operation*:

- ``insert()`` sends one ``INSERT DATA { ... }`` statement per call.
- ``remove()`` sends one ``DELETE DATA { ... }`` statement per call.

As a result, each call is executed atomically by Fuseki/TDB2 as one update
request. The adapter does not open explicit multi-request transactions over HTTP;
transaction boundaries are request-scoped.

Batching strategy
-----------------
Current behavior is intentionally simple:

- One adapter call -> one HTTP request.
- No chunking/splitting is done in the adapter.
- The full graph payload is serialized into one SPARQL Update body.

This keeps semantics clear and transactional per request. For very large graphs,
you may want to add chunking in a future iteration (for example by payload size)
to reduce request body size and avoid reverse proxy limits.

Single-call insert limits
-------------------------
There is no explicit triple-count limit enforced by this adapter for a single
``insert()`` call. Practical limits depend on infrastructure and runtime
constraints:

- HTTP request body limits (reverse proxy, load balancer, or Fuseki connector).
- Request timeout (adapter ``timeout`` value and upstream timeouts).
- Available memory/CPU on client and Fuseki server while parsing large updates.
- Dataset lock/transaction duration on the server for large write operations.

In practice, large writes can fail with 413/408/5xx or timeout errors depending
on environment configuration. If you expect very large graphs, prefer chunked
inserts (for example by byte-size windows) while keeping each chunk as one
transactional update request.

Blank node handling
-------------------
Blank nodes are filtered out in ``insert()`` and ``remove()`` payload builders,
matching the behavior used in the Oxigraph adapter. This avoids ambiguous blank
node identity across request boundaries.

Query behavior
--------------
- Read queries (``SELECT``, ``ASK``, ``CONSTRUCT``, ``DESCRIBE``) are sent to
  ``/query``.
- Update queries (``INSERT``, ``DELETE``, ``WITH``, ``DROP``, etc.) are sent to
  ``/update``.
- Results are mapped to RDFLib-compatible structures:
  - JSON SPARQL results -> iterable of ``ResultRow`` (or ``ASK`` result)
  - RDF payloads (N-Triples/Turtle) -> ``rdflib.Graph``
"""

import json
import logging
import re
import threading
import time
from typing import Any, Tuple, Union

import rdflib
import requests
from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStorePort,
    OntologyEvent,
)
from rdflib import BNode, Graph, URIRef

logger = logging.getLogger(__name__)

# Retryable HTTP status codes for Fuseki write-lock conflicts.
_RETRYABLE_STATUS = {500, 503}
_WRITE_RETRY_ATTEMPTS = 3
_WRITE_RETRY_BACKOFF_BASE = 0.5  # seconds; doubled on each attempt


class ApacheJenaTDB2(ITripleStorePort):
    """HTTP adapter for Apache Jena Fuseki datasets backed by TDB2.

    Concurrency notes
    -----------------
    TDB2 uses a Multiple-Readers / Single-Writer (MRSW) lock model.  Concurrent
    write transactions will conflict on the server and typically produce HTTP 500
    responses.  To avoid this, the adapter serialises *all write operations*
    through a per-instance ``threading.Lock``.  Read-only SPARQL queries bypass
    the lock and are allowed to execute concurrently.

    Additionally, write requests are retried up to ``_WRITE_RETRY_ATTEMPTS``
    times with exponential back-off so that transient lock conflicts from
    *other* clients (e.g. multiple adapter instances pointing at the same
    Fuseki server) are handled gracefully.
    """

    def __init__(
        self,
        jena_tdb2_url: str = "http://localhost:3030/ds",
        timeout: int = 60,
        write_retry_attempts: int = _WRITE_RETRY_ATTEMPTS,
        write_retry_backoff_base: float = _WRITE_RETRY_BACKOFF_BASE,
    ):
        self.jena_tdb2_url = jena_tdb2_url.rstrip("/")
        self.query_endpoint = f"{self.jena_tdb2_url}/query"
        self.update_endpoint = f"{self.jena_tdb2_url}/update"
        self.data_endpoint = f"{self.jena_tdb2_url}/data"
        self.timeout = timeout
        self.write_retry_attempts = write_retry_attempts
        self.write_retry_backoff_base = write_retry_backoff_base

        # Serialise concurrent write operations to avoid TDB2 MRSW lock conflicts.
        self._write_lock = threading.Lock()

        # Reuse TCP connections across requests.
        self._session = requests.Session()

        self._test_connection()

        logger.info("ApacheJenaTDB2 adapter initialized: %s", self.jena_tdb2_url)

    def _test_connection(self):
        response = self._session.get(
            self.query_endpoint,
            params={"query": "ASK { ?s ?p ?o }"},
            timeout=self.timeout,
        )
        response.raise_for_status()

    def _post_write(self, data: bytes) -> requests.Response:
        """Send a SPARQL Update request, serialising through the write lock.

        Retries on retryable HTTP errors (e.g. 500 from TDB2 lock timeout) with
        exponential back-off before re-raising the last exception.
        """
        last_exc: Exception | None = None
        with self._write_lock:
            for attempt in range(self.write_retry_attempts):
                try:
                    response = self._session.post(
                        self.update_endpoint,
                        headers={"Content-Type": "application/sparql-update"},
                        data=data,
                        timeout=self.timeout,
                    )
                    if response.status_code not in _RETRYABLE_STATUS:
                        response.raise_for_status()
                        return response
                    # Retryable error — log and back off before next attempt.
                    logger.warning(
                        "Fuseki write returned %s (attempt %d/%d), retrying...",
                        response.status_code,
                        attempt + 1,
                        self.write_retry_attempts,
                    )
                    last_exc = requests.HTTPError(response=response)
                except requests.exceptions.RequestException as exc:
                    logger.warning(
                        "Fuseki write request failed (attempt %d/%d): %s",
                        attempt + 1,
                        self.write_retry_attempts,
                        exc,
                    )
                    last_exc = exc

                if attempt < self.write_retry_attempts - 1:
                    time.sleep(self.write_retry_backoff_base * (2**attempt))

        raise last_exc  # type: ignore[misc]

    def __remove_blank_nodes(self, triples: Graph) -> Graph:
        clean_graph = Graph()
        for s, p, o in triples:
            if (
                not isinstance(s, BNode)
                and not isinstance(p, BNode)
                and not isinstance(o, BNode)
            ):
                clean_graph.add((s, p, o))

        for prefix, namespace in triples.namespaces():
            clean_graph.bind(prefix, namespace)

        return clean_graph

    def __build_data_update(
        self,
        operation: str,
        triples: Graph,
        graph_name: URIRef | None = None,
    ) -> str:
        statements: list[str] = []
        for s, p, o in triples:
            if isinstance(s, BNode) or isinstance(p, BNode) or isinstance(o, BNode):
                continue
            statements.append(f"  {s.n3()} {p.n3()} {o.n3()} .")

        if graph_name is None:
            return f"{operation} {{\n" + "\n".join(statements) + "\n}"

        return (
            f"{operation} {{\n"
            + f"  GRAPH <{str(graph_name)}> {{\n"
            + "\n".join(statements)
            + "\n  }\n}"
        )

    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        if len(triples) == 0:
            return

        insert_query = self.__build_data_update(
            "INSERT DATA", triples, graph_name=graph_name
        )
        self._post_write(insert_query.encode("utf-8"))

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        if len(triples) == 0:
            return

        delete_query = self.__build_data_update(
            "DELETE DATA", triples, graph_name=graph_name
        )
        self._post_write(delete_query.encode("utf-8"))

    def get(self) -> Graph:
        result = self.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")
        if isinstance(result, Graph):
            return result
        return Graph()

    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        pass

    def __is_update_query(self, query: str) -> bool:
        stripped = re.sub(
            r"(?is)^\s*(?:(?:(?:PREFIX\s+[^\s:]*:\s*<[^>]+>)|(?:BASE\s*<[^>]+>))\s*)*",
            "",
            query,
        ).strip()
        query_upper = stripped.upper()

        return any(
            query_upper.startswith(cmd)
            for cmd in [
                "INSERT",
                "DELETE",
                "CREATE",
                "DROP",
                "CLEAR",
                "LOAD",
                "COPY",
                "MOVE",
                "ADD",
                "WITH",
            ]
        )

    def query(self, query: str) -> Any:
        is_update = self.__is_update_query(query)

        if is_update:
            response = self._post_write(query.encode("utf-8"))
        else:
            response = self._session.post(
                self.query_endpoint,
                headers={
                    "Content-Type": "application/sparql-query",
                    "Accept": "application/sparql-results+json,application/n-triples,text/turtle",
                },
                data=query.encode("utf-8"),
                timeout=self.timeout,
            )
            response.raise_for_status()

        if is_update:
            return rdflib.query.Result("SELECT")

        content_type = response.headers.get("Content-Type", "")

        if "sparql-results" in content_type:
            result_data = json.loads(response.text)

            if "boolean" in result_data:
                ask_result = rdflib.query.Result("ASK")
                ask_result.askAnswer = bool(result_data["boolean"])
                return ask_result

            from rdflib.query import ResultRow
            from rdflib.term import BNode, Literal, URIRef, Variable

            vars = result_data.get("head", {}).get("vars", [])
            bindings = result_data.get("results", {}).get("bindings", [])

            var_objects = [Variable(var) for var in vars]
            results = []

            for binding in bindings:
                row_values = {}
                for var in vars:
                    var_obj = Variable(var)
                    if var in binding:
                        binding_info = binding[var]
                        value_str = binding_info["value"]
                        binding_type = binding_info.get("type", "literal")

                        value: Union[URIRef, BNode, Literal, None]
                        if binding_type == "uri":
                            value = URIRef(value_str)
                        elif binding_type == "bnode":
                            value = BNode(value_str)
                        else:
                            datatype = binding_info.get("datatype")
                            lang = binding_info.get("xml:lang")

                            if datatype:
                                value = Literal(value_str, datatype=URIRef(datatype))
                            elif lang:
                                value = Literal(value_str, lang=lang)
                            else:
                                value = Literal(value_str)

                        row_values[var_obj] = value
                    else:
                        row_values[var_obj] = None  # type: ignore

                results.append(ResultRow(row_values, var_objects))

            return iter(results)  # type: ignore

        if "n-triples" in content_type or "turtle" in content_type:
            graph = Graph()
            format_type = "nt" if "n-triples" in content_type else "turtle"
            graph.parse(data=response.text, format=format_type)
            return graph  # type: ignore

        raise ValueError(f"Unexpected content type: {content_type}")

    def query_view(self, view: str, query: str) -> Any:
        return self.query(query)

    def get_subject_graph(self, subject: URIRef, graph_name: str | URIRef) -> Graph:
        query = f"""
        CONSTRUCT {{ <{str(subject)}> ?p ?o . }}
        WHERE {{ 
            GRAPH <{str(graph_name)}> 
            {{ <{str(subject)}> ?p ?o . }} 
        }}
        """
        result = self.query(query)
        if isinstance(result, Graph):
            return result
        return Graph()

    def create_graph(self, graph_name: URIRef) -> None:
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)
        self.query(f"CREATE GRAPH <{str(graph_name)}>")

    def clear_graph(self, graph_name: URIRef) -> None:
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)
        self.query(f"CLEAR GRAPH <{str(graph_name)}>")

    def drop_graph(self, graph_name: URIRef) -> None:
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)
        self.query(f"DROP GRAPH <{str(graph_name)}>")

    def list_graphs(self) -> list[URIRef]:
        result = self.query("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }")
        graphs: list[URIRef] = []
        for row in result:
            graph = getattr(row, "g", None)
            if isinstance(graph, URIRef):
                graphs.append(graph)
        return graphs
