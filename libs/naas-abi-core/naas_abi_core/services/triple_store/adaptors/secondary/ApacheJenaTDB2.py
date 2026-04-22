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

Retry behaviour on transient server errors
------------------------------------------
Fuseki/TDB2 uses a Multi-Reader/Single-Writer (MRSW) lock at the dataset level.
Under concurrent write load the server may reject a write request with HTTP 500
or 503 while the lock is held by another transaction.  These failures are
*transient* – a short wait is usually enough for the lock to be released.

The adapter handles this automatically:

- ``max_retries`` (default: 3) controls how many additional attempts are made
  after the first failure.
- ``retry_delay`` (default: 0.5 s) is the base delay; actual wait time grows
  exponentially (``retry_delay * 2 ** attempt``) with a small random jitter to
  reduce thundering-herd effects.
- Only HTTP 500 and 503 responses trigger a retry.  All other errors (4xx,
  connection errors, etc.) are raised immediately.

Write serialisation (distributed lock)
---------------------------------------
By default the adapter uses a ``threading.Lock`` to prevent concurrent writes
from the *same process* reaching Fuseki simultaneously.  For multi-process or
multi-instance deployments — where multiple adapter instances point at the same
Fuseki dataset — you can inject a ``KeyValueService`` to promote that lock to a
*distributed* lock:

.. code-block:: python

    from naas_abi_core.services.keyvalue.KeyValueFactory import (
        KeyValueServiceFactory,
    )
    kv = KeyValueServiceFactory.KeyValueServiceRedis(redis_url="redis://...")
    adapter = ApacheJenaTDB2(
        jena_tdb2_url="http://...",
        key_value_service=kv,
    )

When a ``KeyValueService`` is provided:

- Acquisition uses ``set_if_not_exists(key, token, ttl=timeout+10)`` — atomic
  across processes via the underlying store (e.g. Redis).
- Release uses ``delete_if_value_matches(key, token)`` — only the holder can
  release the lock (prevents accidentally releasing another holder's lock after
  a retry).
- The lock key is derived from the dataset URL so each dataset gets its own
  lock namespace.
- The TTL is ``timeout + 10 s`` — long enough to cover the write plus retries,
  short enough to self-heal after a crash.
- Lock acquisition uses the same exponential back-off as HTTP retries.

If no ``KeyValueService`` is provided, the adapter falls back to the
``threading.Lock`` (existing behaviour, no extra dependency required).

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

import hashlib
import json
import logging
import os
import random
import re
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Generator, Optional, Tuple, Union

if TYPE_CHECKING:
    from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService

import rdflib
import requests
from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStorePort,
    OntologyEvent,
)
from rdflib import BNode, Graph, URIRef

logger = logging.getLogger(__name__)


class ApacheJenaTDB2(ITripleStorePort):
    """HTTP adapter for Apache Jena Fuseki datasets backed by TDB2."""

    def __init__(
        self,
        jena_tdb2_url: str = "http://localhost:3030/ds",
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        key_value_service: Optional["KeyValueService"] = None,
    ):
        self.jena_tdb2_url = jena_tdb2_url.rstrip("/")
        self.query_endpoint = f"{self.jena_tdb2_url}/query"
        self.update_endpoint = f"{self.jena_tdb2_url}/update"
        self.data_endpoint = f"{self.jena_tdb2_url}/data"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session = requests.Session()
        self._key_value_service = key_value_service
        # Stable lock key scoped to this dataset URL so each Fuseki dataset
        # gets its own lock namespace in the key-value store.
        _url_hash = hashlib.sha256(jena_tdb2_url.encode()).hexdigest()[:16]
        self._dataset_lock_key = f"fuseki:write_lock:{_url_hash}"
        # Fallback thread lock used when no KeyValueService is provided.
        self._write_lock = threading.Lock()

        self._test_connection()

        logger.info("ApacheJenaTDB2 adapter initialized: %s", self.jena_tdb2_url)

    def _test_connection(self):
        response = self._session.get(
            self.query_endpoint,
            params={"query": "ASK { ?s ?p ?o }"},
            timeout=self.timeout,
        )
        response.raise_for_status()

    # ------------------------------------------------------------------
    # Internal HTTP helpers with retry
    # ------------------------------------------------------------------

    _RETRYABLE_STATUS_CODES = frozenset({500, 503})

    @contextmanager
    def _acquire_write_lock(self) -> Generator[None, None, None]:
        """Acquire a write lock appropriate for the deployment topology.

        - With a ``KeyValueService``: acquires a distributed lock via
          ``set_if_not_exists`` so writes are serialised across all processes
          and service instances pointing at the same Fuseki dataset.
        - Without: acquires ``self._write_lock`` (``threading.Lock``) to
          serialise writes within the current process only.

        In both cases the same exponential back-off / retry parameters
        (``max_retries``, ``retry_delay``) are used for acquisition attempts.
        """
        if self._key_value_service is None:
            with self._write_lock:
                yield
            return

        # --- Distributed lock path ---
        # Each acquisition uses a unique random token so that only the exact
        # caller that acquired the lock can release it (prevents accidental
        # release of another holder's lock after a long retry pause).
        lock_token = os.urandom(16)
        # TTL = request timeout + buffer; self-heals after process crash.
        lock_ttl = self.timeout + 10

        acquired = False
        for attempt in range(self.max_retries + 1):
            if self._key_value_service.set_if_not_exists(
                self._dataset_lock_key, lock_token, ttl=lock_ttl
            ):
                acquired = True
                break
            if attempt < self.max_retries:
                delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(
                    "Fuseki distributed write lock busy (attempt %d/%d); waiting %.2fs",
                    attempt + 1,
                    self.max_retries + 1,
                    delay,
                )
                time.sleep(delay)

        if not acquired:
            raise RuntimeError(
                f"Could not acquire distributed write lock for {self.jena_tdb2_url} "
                f"after {self.max_retries + 1} attempts"
            )

        try:
            yield
        finally:
            self._key_value_service.delete_if_value_matches(
                self._dataset_lock_key, lock_token
            )

    def _post_update(self, sparql: str) -> requests.Response:
        """POST to the SPARQL update endpoint, retrying on transient 500/503.

        The write lock (thread-local or distributed) is held for the full
        duration of the attempt loop so that only one write transaction is
        in-flight at a time.
        """
        with self._acquire_write_lock():
            last_response: requests.Response | None = None
            for attempt in range(self.max_retries + 1):
                response = self._session.post(
                    self.update_endpoint,
                    headers={"Content-Type": "application/sparql-update"},
                    data=sparql.encode("utf-8"),
                    timeout=self.timeout,
                )
                if response.status_code in self._RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                    logger.warning(
                        "Fuseki update returned HTTP %d (attempt %d/%d); retrying in %.2fs",
                        response.status_code,
                        attempt + 1,
                        self.max_retries + 1,
                        delay,
                    )
                    last_response = response
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response
            # All retries exhausted – raise from the last response.
            assert last_response is not None
            last_response.raise_for_status()
            return last_response  # unreachable, satisfies type checker

    def _post_query(self, sparql: str) -> requests.Response:
        """POST to the SPARQL query endpoint, retrying on transient 500/503.

        Read queries are not serialised by the write lock — Fuseki/TDB2 allows
        concurrent readers.
        """
        last_response: requests.Response | None = None
        for attempt in range(self.max_retries + 1):
            response = self._session.post(
                self.query_endpoint,
                headers={
                    "Content-Type": "application/sparql-query",
                    "Accept": "application/sparql-results+json,application/n-triples,text/turtle",
                },
                data=sparql.encode("utf-8"),
                timeout=self.timeout,
            )
            if response.status_code in self._RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                delay = self.retry_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(
                    "Fuseki query returned HTTP %d (attempt %d/%d); retrying in %.2fs",
                    response.status_code,
                    attempt + 1,
                    self.max_retries + 1,
                    delay,
                )
                last_response = response
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response
        assert last_response is not None
        last_response.raise_for_status()
        return last_response  # unreachable

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
        self._post_update(insert_query)

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        if len(triples) == 0:
            return

        delete_query = self.__build_data_update(
            "DELETE DATA", triples, graph_name=graph_name
        )
        self._post_update(delete_query)

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
            response = self._post_update(query)
        else:
            response = self._post_query(query)

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

    def clear_graph(self, graph_name: URIRef | None = None) -> None:
        if graph_name is None:
            self.query("CLEAR DEFAULT")
        else:
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
