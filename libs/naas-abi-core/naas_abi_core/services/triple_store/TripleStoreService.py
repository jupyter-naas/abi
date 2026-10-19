import base64
import hashlib
import io
import os
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import Any

import rdflib
from naas_abi_core import logger
from naas_abi_core.services.iam.enforcement import ResourceGuard
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.triple_store import sparql_access as sparql
from naas_abi_core.services.triple_store.iam_catalog import CATALOG, GRAPH, VIEW
from naas_abi_core.services.triple_store.ontologies.modules.TripleStoreEventOntology import (
    GraphCleared,
    GraphCreated,
    GraphDropped,
    SchemaLoaded,
    SchemaRemoved,
    TriplesInserted,
    TriplesRemoved,
    TripleStoreError,
)
from naas_abi_core.services.triple_store.TripleStorePorts import (
    DatasetRestrictionUnsupported,
    Exceptions,
    ITripleStorePort,
    ITripleStoreService,
    OntologyEvent,
    QueryDataset,
    QueryStream,
    Triple,
    checked_iri,
)
from rdflib import Graph, URIRef


@dataclass(frozen=True)
class _SchemaIndexEntry:
    subject: URIRef
    hash: str
    file_last_update_time: str


SCHEMA_TTL = """
@prefix internal: <http://triple-store.internal#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

internal:Schema a owl:Class ;
    rdfs:label "Schema" ;
    rdfs:comment "Represents a schema file that has been loaded into the triple store" .

internal:hash a owl:DatatypeProperty ;
    rdfs:domain internal:Schema ;
    rdfs:range xsd:string ;
    rdfs:label "hash" ;
    rdfs:comment "SHA-256 hash of the schema content" .

internal:fileLastUpdateTime a owl:DatatypeProperty ;
    rdfs:domain internal:Schema ;
    rdfs:range xsd:dateTime ;
    rdfs:label "file last update time" ;
    rdfs:comment "Last modification timestamp of the schema file" .

internal:filePath a owl:DatatypeProperty ;
    rdfs:domain internal:Schema ;
    rdfs:range xsd:string ;
    rdfs:label "file path" ;
    rdfs:comment "Path to the schema file" .

internal:content a owl:DatatypeProperty ;
    rdfs:domain internal:Schema ;
    rdfs:range xsd:base64Binary ;
    rdfs:label "content" ;
    rdfs:comment "Base64 encoded content of the schema file" .
"""
GRAPH_CLASS = URIRef("http://ontology.naas.ai/abi/Graph")
_SCHEMA_GRAPH = URIRef("http://ontology.naas.ai/graph/schema")
_SCHEMA_CLASS = URIRef("http://triple-store.internal#Schema")
_OWL_CLASS = URIRef("http://www.w3.org/2002/07/owl#Class")
_SCHEMA_BOOTSTRAP_ASK = f"""
ASK WHERE {{
  GRAPH <{_SCHEMA_GRAPH}> {{
    <{_SCHEMA_CLASS}> a <{_OWL_CLASS}>
  }}
}}
"""


# What a SPARQL Update may need, besides reading (sparql_access).
_UPDATE_ACTIONS = (
    "Query",
    "Insert",
    "Remove",
    "ClearGraph",
    "DropGraph",
    "CreateGraph",
)
# Every triple of a query's default graph: a confined dump or export.
_EVERYTHING = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"


class TripleStoreService(ServiceBase, ITripleStoreService):
    """TripleStoreService provides CRUD operations and SPARQL querying capabilities for ontologies.

    This service acts as a facade for ontology storage and retrieval operations. It handles storing,
    retrieving, merging and querying of RDF ontologies while providing optional filtering of
    non-named individuals.

    Attributes:
        __triple_store_adapter (ITripleStorePort): The storage adapter implementation used for
            persisting and retrieving ontologies.

    Example:
        >>> store = TripleStoreService(FileSystemTripleStore("ontologies/"))
        >>> ontology = Graph()
        >>> # ... populate ontology ...
        >>> store.store("my_ontology", ontology)
        >>> results = store.query("SELECT ?s WHERE { ?s a owl:Class }")

    Wired into an engine, every operation is authorized per graph,
    ``graph/<iri>`` (``graph/default`` for the default graph), RFC §6.4:

    * a SPARQL query (``query``, ``query_stream``, ``query_view``) by a caller
      who may not read every graph names only graphs it may read (``FROM``,
      ``FROM NAMED``, ``GRAPH <iri>``; else ``GraphNotFoundError`` or
      ``PermissionDeniedError``), and runs over the graphs it may read: the
      store gets the dataset, so ``GRAPH ?g`` and the default graph see only
      those. ``SERVICE`` needs every graph. A store that cannot confine a
      query refuses it;
    * a SPARQL Update needs the matching action on each graph it touches
      (``sparql_access``);
    * ``list_graphs``, ``get``, ``export`` and ``get_subject_graph`` without a
      graph hold only the graphs the caller may read.
    """

    def __init__(
        self,
        triple_store_adapter: ITripleStorePort,
    ):
        super().__init__()
        self.__triple_store_adapter = triple_store_adapter
        self.__schema_graph = _SCHEMA_GRAPH
        self._guard = ResourceGuard.of(CATALOG, self)
        self._bootstrap_schema_graph()

    @property
    def adapter(self) -> ITripleStorePort:
        """The wrapped secondary adapter -- public so callers (e.g.
        ``EngineNATSLoader``) can check what kind of adapter this service is
        backed by, mirroring ``ObjectStorageService.adapter``."""
        return self.__triple_store_adapter

    def _schema_graph_bootstrapped(self) -> bool:
        """Return True when the built-in schema vocabulary is already in the store.

        Read-only ASK — no distributed write lock — so Dagster run workers that
        only need to check boot state do not contend with active writers.
        """
        try:
            result = self.__triple_store_adapter.query(_SCHEMA_BOOTSTRAP_ASK)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "TripleStoreService: schema bootstrap probe failed (%s) — "
                "will attempt insert",
                exc,
            )
            return False

        ask_answer = getattr(result, "askAnswer", None)
        if ask_answer is not None:
            return bool(ask_answer)

        if isinstance(result, rdflib.query.Result) and result.type == "ASK":
            return bool(result.askAnswer)

        logger.debug(
            "TripleStoreService: schema bootstrap probe returned unexpected "
            "%r — will attempt insert",
            type(result),
        )
        return False

    def _bootstrap_schema_graph(self) -> None:
        if self._schema_graph_bootstrapped():
            logger.debug(
                "TripleStoreService: schema graph already present — skip bootstrap insert"
            )
            return

        schema_ttl_buffer = io.StringIO(SCHEMA_TTL)
        self.insert(
            Graph().parse(schema_ttl_buffer, format="turtle"),
            graph_name=self.__schema_graph,
        )

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        try:
            if not self.services.events_available():
                return
            self.services.events.emit(event)
        except Exception as exc:  # noqa: BLE001
            # Triple store mutations are the source of truth; event logging must not break them.
            logger.warning(f"TripleStoreService: failed to publish event: {exc}")

    @staticmethod
    def _error_message(exc: Exception) -> str:
        """Build a rich, loggable message from an adapter exception.

        HTTP-backed adapters (e.g. Apache Jena Fuseki) raise
        :class:`Exceptions.RequestError`, which carries the server's own status
        code and response body — the actual cause of a 5xx (OOM, disk-full, lock
        abort, TDB2 stack trace). Surface that detail so the persisted
        ``TripleStoreError`` event is genuinely diagnosable instead of a generic
        "500 Server Error" string. Any other exception falls back to ``str``.
        """
        if isinstance(exc, Exceptions.RequestError):
            return exc.detail()
        return str(exc)

    # -- authorization (RFC §6.4) ------------------------------------------------

    def __graph(
        self, action: str, graph: URIRef | str, *, parsed: bool = False
    ) -> None:
        """Require ``action`` on a graph. The name must be an IRI before
        anything else: the name IAM checks is the one a store runs. That holds
        for one the SPARQL parser found (``parsed``) too: rdflib keeps the
        backslash of an escaped prefixed name (``g:\\/x``) that the store drops,
        so only the literal ``default`` is taken as is."""
        iri = (
            str(graph)
            if parsed and graph == sparql.DEFAULT_GRAPH
            else checked_iri(graph)
        )
        self._guard.require(
            action,
            GRAPH,
            iri,
            not_found=lambda: Exceptions.GraphNotFoundError(f"Graph {iri} not found"),
        )

    @staticmethod
    def __parsed_name(graph: URIRef | str) -> None:
        """A graph name the SPARQL parser found must be an IRI (see ``__graph``).
        ``default`` and ``*`` name the default graph and every graph."""
        if graph not in (sparql.DEFAULT_GRAPH, sparql.EVERY_GRAPH):
            checked_iri(graph)

    def __every(self, action: str) -> None:
        if not self._guard.allows_every(action, GRAPH):
            raise PermissionDeniedError(
                self._guard.action(action),
                message=f"{action} on every graph is not allowed to this caller",
            )

    def __confined(self, action: str) -> bool:
        """Whether ``action`` must be confined to some graphs for the caller."""
        return self._guard.iam is not None and not self._guard.allows_every(
            action, GRAPH
        )

    def __dataset(self, action: str, shape: sparql.ReadShape) -> QueryDataset:
        """The graphs a confined read runs over."""
        if shape.has_dataset:
            return QueryDataset(False, shape.from_graphs, shape.from_named)
        named = tuple(
            self._guard.filter(
                action,
                GRAPH,
                self.__triple_store_adapter.list_graphs(),
                lambda graph: str(graph),
            )
        )
        union = getattr(self.__triple_store_adapter, "union_default_graph", False)
        return QueryDataset(
            self._guard.allowed(action, GRAPH, sparql.DEFAULT_GRAPH),
            named if union else (),
            named,
        )

    def __authorize_request(
        self, action: str, request: str, *, updates: bool = True
    ) -> QueryDataset | None:
        """Authorize a SPARQL request, parsed once (``sparql_access.analyze``).

        An update needs the matching action on each graph it touches; a query
        names only graphs the caller may read and runs over them. Returns the
        dataset a confined query runs over, or None when it runs as is.

        ``updates=False`` (a view): an update is refused for every caller,
        broad ones included, so the request is always parsed.
        """
        if self._guard.iam is None:
            return None
        analysis = None if updates else self.__analyze(request)
        if analysis is not None and analysis.update:
            raise Exceptions.InvalidRequest("A SPARQL update is not a query")
        actions = (action, *_UPDATE_ACTIONS) if updates else (action,)
        if all(self._guard.allows_every(a, GRAPH) for a in actions):
            return None
        if analysis is None:
            analysis = self.__analyze(request)
        if analysis.update:
            # Every name an IRI before any check: no answer depends on a later one.
            for need in analysis.needs:
                self.__parsed_name(need.graph)
            for need in analysis.needs:
                if need.graph == sparql.EVERY_GRAPH:
                    self.__every(need.action)
                else:
                    self.__graph(need.action, need.graph, parsed=True)
            return None
        if not self.__confined(action):
            return None
        shape = analysis.shape
        for graph in shape.named:
            self.__parsed_name(graph)
        for graph in shape.named:
            self.__graph(action, graph, parsed=True)
        if shape.service:
            raise PermissionDeniedError(
                self._guard.action(action),
                message=f"SERVICE needs {action} on every graph",
            )
        return self.__dataset(action, shape)

    def __analyze(self, request: str) -> sparql.Analysis:
        return sparql.analyze(
            request,
            union_default_graph=getattr(
                self.__triple_store_adapter, "union_default_graph", False
            ),
        )

    def __confined_query(self, query: str, dataset: QueryDataset) -> Any:
        try:
            return self.__triple_store_adapter.query_dataset(query, dataset)
        except DatasetRestrictionUnsupported as exc:
            raise PermissionDeniedError(
                self._guard.action("Query"), message=str(exc)
            ) from exc

    def _hash_value(self, value: object) -> str:
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:32]

    def _subscription_graph_topic_token(self, graph_name: URIRef | str) -> str:
        if graph_name == "*":
            return "*"
        return self._hash_value(graph_name)

    def insert(
        self,
        triples: Graph,
        graph_name: URIRef,
    ) -> None:
        assert graph_name is not None
        self.__graph("Insert", graph_name)

        # Insert the triples into the store
        try:
            self.__triple_store_adapter.insert(triples, graph_name=graph_name)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="insert",
                    graph_name=str(graph_name),
                    message=self._error_message(exc),
                )
            )
            raise

        self.__publish_event(
            TriplesInserted(
                graph_name=str(graph_name),
                triple_count=len(triples),
            )
        )

        if self.services_wired is False:
            return

        # Notify listeners of the insert. Batched: a bulk load (an ontology
        # file, an import) produces one message per triple, and a per-message
        # round-trip to the bus makes engine boot scale with triple count.
        self.__publish_triples("insert", triples, graph_name)

    def remove(
        self,
        triples: Graph,
        graph_name: URIRef,
    ) -> None:
        assert graph_name is not None
        self.__graph("Remove", graph_name)

        # Remove the triples from the store
        try:
            self.__triple_store_adapter.remove(triples, graph_name=graph_name)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="remove",
                    graph_name=str(graph_name),
                    message=self._error_message(exc),
                )
            )
            raise

        self.__publish_event(
            TriplesRemoved(
                graph_name=str(graph_name),
                triple_count=len(triples),
            )
        )

        if self.services_wired is False:
            return

        # Notify listeners of the delete
        self.__publish_triples("delete", triples, graph_name)

    def __publish_triples(
        self, operation: str, triples: Graph, graph_name: URIRef
    ) -> None:
        """Broadcast one bus message per triple, in a single batch.

        Routing keys are unchanged (``ts.<operation>.g.<h>.s.<h>.p.<h>.o.<h>``),
        so subscriber bindings keep matching exactly as before.
        """
        graph_hash = self._hash_value(str(graph_name))
        messages: list[tuple[str, bytes]] = []
        for s, p, o in triples.triples((None, None, None)):
            routing_key = (
                f"ts.{operation}.g.{graph_hash}"
                f".s.{self._hash_value(s)}"
                f".p.{self._hash_value(p)}"
                f".o.{self._hash_value(o)}"
            )
            messages.append((routing_key, f"{s.n3()} {p.n3()} {o.n3()} .\n".encode()))
        if not messages:
            return
        try:
            self.services.bus.publish_many("triple_store", messages)
        except Exception as e:
            logger.error(f"Error publishing triples: {e}")
            raise

    def get(self) -> Graph:
        """The store as its adapter dumps it; only the readable graphs for a
        caller who may not read every graph."""
        if not self.__confined("Get"):
            return self.__triple_store_adapter.get()
        result = self.__confined_query(
            _EVERYTHING, self.__dataset("Get", sparql.ReadShape())
        )
        return result if isinstance(result, Graph) else Graph() + result.graph

    def query(self, query: str) -> rdflib.query.Result:
        dataset = self.__authorize_request("Query", query)
        if dataset is not None:
            return self.__confined_query(query, dataset)
        try:
            return self.__triple_store_adapter.query(query)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="query",
                    message=self._error_message(exc),
                )
            )
            raise

    @contextmanager
    def query_stream(self, query: str) -> Iterator[QueryStream]:
        dataset = self.__authorize_request("QueryStream", query)
        with ExitStack() as stack:
            try:
                result = stack.enter_context(
                    self.__triple_store_adapter.query_stream(query)
                    if dataset is None
                    else self.__triple_store_adapter.query_stream_dataset(
                        query, dataset
                    )
                )
            except DatasetRestrictionUnsupported as exc:
                raise PermissionDeniedError(
                    self._guard.action("QueryStream"), message=str(exc)
                ) from exc
            except Exception as exc:
                self.__report_stream_error(exc)
                raise
            result.rows = self.__reporting_errors(result.rows)
            result.triples = self.__reporting_errors(result.triples)
            yield result

    @contextmanager
    def export(self, graph_name: URIRef | None = None) -> Iterator[Iterator[Triple]]:
        confined = None
        if graph_name is not None:
            self.__graph("Export", graph_name)
        elif self.__confined("Export"):
            confined = self.__dataset("Export", sparql.ReadShape())
        with ExitStack() as stack:
            try:
                if confined is None:
                    triples = stack.enter_context(
                        self.__triple_store_adapter.export(graph_name)
                    )
                else:
                    triples = stack.enter_context(
                        self.__triple_store_adapter.query_stream_dataset(
                            _EVERYTHING, confined
                        )
                    ).triples
            except DatasetRestrictionUnsupported as exc:
                raise PermissionDeniedError(
                    self._guard.action("Export"), message=str(exc)
                ) from exc
            except Exception as exc:
                self.__report_stream_error(exc, "export", graph_name)
                raise
            yield self.__reporting_errors(triples, "export", graph_name)

    def __reporting_errors(
        self,
        items: Iterator,
        operation: str = "query_stream",
        graph_name: URIRef | None = None,
    ) -> Iterator:
        # Errors raised while reading the backend, not by the caller's own block.
        try:
            yield from items
        except Exception as exc:
            self.__report_stream_error(exc, operation, graph_name)
            raise

    def __report_stream_error(
        self,
        exc: Exception,
        operation: str = "query_stream",
        graph_name: URIRef | None = None,
    ) -> None:
        self.__publish_event(
            TripleStoreError(
                operation=operation,
                graph_name=str(graph_name) if graph_name is not None else None,
                message=self._error_message(exc),
            )
        )

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        """``QueryView`` on the view, and ``Query`` rules on the graphs it reads:
        confined, it runs as a query over the caller's graphs."""
        self._guard.require(
            "QueryView",
            VIEW,
            view,
            not_found=lambda: Exceptions.ViewNotFoundError(f"View {view} not found"),
        )
        dataset = self.__authorize_request("Query", query, updates=False)
        if dataset is not None:
            return self.__confined_query(query, dataset)
        try:
            return self.__triple_store_adapter.query_view(view, query)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="query_view",
                    message=self._error_message(exc),
                )
            )
            raise

    def create_graph(self, graph_name: URIRef) -> None:
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)
        checked_iri(graph_name)
        commit = self._guard.create(
            "CreateGraph",
            GRAPH,
            str(graph_name),
            exists=lambda: graph_name in self.__triple_store_adapter.list_graphs(),
            not_found=lambda: Exceptions.GraphNotFoundError(
                f"Graph {graph_name} not found"
            ),
        )

        try:
            self.__triple_store_adapter.create_graph(graph_name)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="create_graph",
                    graph_name=str(graph_name),
                    message=self._error_message(exc),
                )
            )
            raise

        commit()
        self.__publish_event(GraphCreated(graph_name=str(graph_name)))

    def clear_graph(self, graph_name: URIRef) -> None:
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)
        self.__graph("ClearGraph", graph_name)

        try:
            self.__triple_store_adapter.clear_graph(graph_name)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="clear_graph",
                    graph_name=str(graph_name),
                    message=self._error_message(exc),
                )
            )
            raise

        self.__publish_event(GraphCleared(graph_name=str(graph_name)))

    def drop_graph(self, graph_name: URIRef) -> None:
        self.__graph("DropGraph", graph_name)
        try:
            self.__triple_store_adapter.drop_graph(graph_name)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="drop_graph",
                    graph_name=str(graph_name),
                    message=self._error_message(exc),
                )
            )
            raise

        self._guard.forget(GRAPH, str(graph_name))
        self.__publish_event(GraphDropped(graph_name=str(graph_name)))

    def list_graphs(self) -> list[URIRef]:
        """The graphs the caller may list (RFC §5.5); never fails for that."""
        return self._guard.filter(
            "ListGraphs",
            GRAPH,
            self.__triple_store_adapter.list_graphs(),
            lambda graph: str(graph),
        )

    def subscribe(
        self,
        topic: tuple[URIRef | None, URIRef | None, URIRef | None],
        callback: Callable[[bytes], None],
        event_type: OntologyEvent | None = None,
        graph_name: URIRef | str = "*",
    ) -> None:
        """Call ``callback`` with the triples inserted into or removed from
        ``graph_name``, as N3. The messages carry triples, not graph names, so
        a subscription is authorized as a read of the graph it names, and of
        every graph for ``*``. It is checked once, when it is made."""
        if graph_name == "*":
            self.__every("Subscribe")
        else:
            self.__graph("Subscribe", graph_name)
        _event_type: str = ""
        if event_type == OntologyEvent.INSERT:
            _event_type = "insert"
        elif event_type == OntologyEvent.DELETE:
            _event_type = "delete"
        elif event_type is None:
            _event_type = "*"

        graph_topic = self._subscription_graph_topic_token(graph_name)
        s = "*" if topic[0] is None else self._hash_value(topic[0])
        p = "*" if topic[1] is None else self._hash_value(topic[1])
        o = "*" if topic[2] is None else self._hash_value(topic[2])

        topic_str = f"ts.{_event_type}.g.{graph_topic}.s.{s}.p.{p}.o.{o}"

        self.services.bus.subscribe(
            "triple_store",
            topic_str,
            callback,
        )

    def get_subject_graph(self, subject: str, graph_name: str = "*") -> Graph:
        """A subject's triples in one graph, or in every graph (``*``); only in
        the graphs the caller may read."""
        checked_iri(subject)
        if graph_name != "*":
            self.__graph("GetSubjectGraph", graph_name)
        elif self.__confined("GetSubjectGraph"):
            named = self.__dataset("GetSubjectGraph", sparql.ReadShape()).named_graphs
            result = self.__confined_query(
                f"CONSTRUCT {{ <{subject}> ?p ?o }} "
                f"WHERE {{ GRAPH ?g {{ <{subject}> ?p ?o }} }}",
                QueryDataset(False, (), named),
            )
            return result if isinstance(result, Graph) else Graph() + result.graph
        return self.__triple_store_adapter.get_subject_graph(
            URIRef(subject), graph_name
        )

    ############################################################
    # Schema Management
    ############################################################

    def _build_schema_index(
        self, filepath_filter: str | None = None
    ) -> dict[str, list[_SchemaIndexEntry]]:
        """Read stored Schema metadata into a plain Python dict.

        The index is keyed by filePath and contains one entry per stored
        Schema subject (lists allow detecting duplicate metadata). We
        intentionally do NOT include `content` here — it can be megabytes
        and is only needed when a file has actually changed (rare). Fetched
        on demand via `_fetch_schema_content`.

        A plain dict is used (rather than an rdflib Graph) because the index
        is read concurrently from multiple worker threads, and rdflib's
        SPARQL/turtle parser uses pyparsing which has thread-unsafe global
        state. Python dicts are safe to read concurrently.
        """
        filter_clause = (
            f'FILTER(STR(?filePath) = "{filepath_filter}") .'
            if filepath_filter is not None
            else ""
        )
        results = self.query(f"""
            PREFIX internal: <http://triple-store.internal#>
            SELECT ?schema ?filePath ?hash ?fileLastUpdateTime
            WHERE {{
                GRAPH <{self.__schema_graph!s}> {{
                    ?schema a internal:Schema ;
                        internal:filePath ?filePath ;
                        internal:hash ?hash ;
                        internal:fileLastUpdateTime ?fileLastUpdateTime .
                    {filter_clause}
                }}
            }}
        """)
        index: dict[str, list[_SchemaIndexEntry]] = {}
        for row in results:
            assert isinstance(row, rdflib.query.ResultRow)
            schema, filePath, h, t = row
            assert isinstance(schema, URIRef)
            index.setdefault(str(filePath), []).append(
                _SchemaIndexEntry(
                    subject=schema,
                    hash=str(h),
                    file_last_update_time=str(t),
                )
            )
        return index

    def _fetch_schema_content(self, subject: URIRef) -> str | None:
        results = self.query(
            f"""
            PREFIX internal: <http://triple-store.internal#>
            SELECT ?content
            WHERE {{
                GRAPH <{self.__schema_graph!s}> {{
                    <{subject!s}> internal:content ?content .
                }}
            }}
            """
        )
        for row in results:
            assert isinstance(row, rdflib.query.ResultRow)
            return str(row[0])
        return None

    def _remove_schema_subject(self, subject: URIRef) -> None:
        triples = self.query(
            f"""
            SELECT ?p ?o
            WHERE {{
                GRAPH <{self.__schema_graph!s}> {{
                    <{subject!s}> ?p ?o .
                }}
            }}
            """
        )
        cleanup_graph = Graph()
        for row in triples:
            assert isinstance(row, rdflib.query.ResultRow)
            p, o = row
            cleanup_graph.add((subject, p, o))
        if len(cleanup_graph) > 0:
            self.remove(cleanup_graph, graph_name=self.__schema_graph)

    def load_schemas(self, filepaths: list[str]):
        """Parallel schema load. See `_apply_schema_for_file` for per-file logic."""
        if not filepaths:
            return

        index = self._build_schema_index()

        # Parallelize per-file work. For unchanged files this is just file I/O
        # + SHA-256 + dict lookup — no Fuseki traffic at all. For changed/new
        # files it also includes Fuseki writes; those overlap across workers.
        # The shared `index` dict is read-only during this loop.
        max_workers = min(8, len(filepaths))
        with ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="ts-schema-load"
        ) as executor:
            futures = [
                executor.submit(
                    self._apply_schema_for_file_with_event,
                    filepath,
                    index.get(filepath, []),
                )
                for filepath in filepaths
            ]
            for future in futures:
                future.result()

    def _apply_schema_for_file_with_event(
        self, filepath: str, entries: list[_SchemaIndexEntry]
    ) -> None:
        try:
            self._apply_schema_for_file(filepath, entries)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="load_schema",
                    filepath=filepath,
                    message=self._error_message(exc),
                )
            )
            raise
        self.__publish_event(SchemaLoaded(filepath=filepath))

    def load_schema(self, filepath: str, schema_cache: Graph | None = None):
        """Single-file schema load. `schema_cache` is accepted for backward
        compatibility but ignored — we always look up via a filtered query."""
        del schema_cache  # legacy param, no longer used
        entries = self._build_schema_index(filepath_filter=filepath).get(filepath, [])
        self._apply_schema_for_file_with_event(filepath, entries)

    def _apply_schema_for_file(
        self, filepath: str, entries: list[_SchemaIndexEntry]
    ) -> None:
        try:
            if not entries:
                self._insert_new_schema(filepath)
                return

            with open(filepath, "r") as file:
                new_content = file.read()
            new_content_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

            matching = next((e for e in entries if e.hash == new_content_hash), None)
            primary = matching if matching is not None else entries[0]
            duplicate_subjects = [
                e.subject for e in entries if e.subject != primary.subject
            ]

            if primary.hash == new_content_hash:
                if duplicate_subjects:
                    logger.debug(
                        f"Cleaning up {len(duplicate_subjects)} duplicate schema "
                        f"metadata entries for {filepath}."
                    )
                    for duplicate_subject in duplicate_subjects:
                        self._remove_schema_subject(duplicate_subject)
                return

            logger.debug(f"Loading schema: '{filepath}'")

            old_content_b64 = self._fetch_schema_content(primary.subject)
            if old_content_b64 is None:
                raise ValueError(
                    f"Schema metadata for '{filepath}' is missing stored content."
                )
            old_content = base64.b64decode(old_content_b64).decode("utf-8")

            old_schema = Graph().parse(io.StringIO(old_content), format="turtle")
            new_schema = Graph().parse(io.StringIO(new_content), format="turtle")

            addition_triples = new_schema - old_schema
            deletion_triples = old_schema - new_schema
            self.insert(addition_triples, graph_name=self.__schema_graph)
            self.remove(deletion_triples, graph_name=self.__schema_graph)

            file_last_update_time = os.path.getmtime(filepath)

            self.remove(
                Graph().parse(
                    io.StringIO(f'''
                @prefix internal: <http://triple-store.internal#> .

                <{primary.subject}> internal:hash "{primary.hash}" ;
                    internal:fileLastUpdateTime "{primary.file_last_update_time}" ;
                    internal:content "{old_content_b64}" .
            '''),
                    format="turtle",
                ),
                graph_name=self.__schema_graph,
            )
            self.insert(
                Graph().parse(
                    io.StringIO(f'''
                @prefix internal: <http://triple-store.internal#> .

                <{primary.subject}> internal:hash "{new_content_hash}" ;
                    internal:fileLastUpdateTime "{file_last_update_time}" ;
                    internal:content "{base64.b64encode(new_content.encode("utf-8")).decode("utf-8")}" .
            '''),
                    format="turtle",
                ),
                graph_name=self.__schema_graph,
            )

            if duplicate_subjects:
                logger.debug(
                    f"Cleaning up {len(duplicate_subjects)} duplicate schema "
                    f"metadata entries for {filepath}."
                )
                for duplicate_subject in duplicate_subjects:
                    self._remove_schema_subject(duplicate_subject)
        except Exception as e:  # noqa: BLE001
            import traceback

            logger.error(f"Error loading schema ({filepath}): {e!s}")
            traceback.print_exc()

    def _insert_new_schema(self, filepath: str) -> None:
        logger.debug("Loading schema in graph as it doesn't exist in store.")

        with open(filepath, "r") as file:
            content = file.read()

        base64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        g = Graph().parse(filepath)
        self.insert(g, graph_name=self.__schema_graph)

        file_last_update_time = os.path.getmtime(filepath)

        self.insert(
            Graph().parse(
                io.StringIO(f'''
            @prefix internal: <http://triple-store.internal#> .

            <http://triple-store.internal/{uuid.uuid4()}> a internal:Schema ;
                internal:hash "{content_hash}" ;
                internal:filePath "{filepath}" ;
                internal:fileLastUpdateTime "{file_last_update_time}" ;
                internal:content "{base64_content}" .
        '''),
                format="turtle",
            ),
            graph_name=self.__schema_graph,
        )

    def remove_schema(self, filepath: str):
        logger.debug(f"Removing schema: {filepath}")

        try:
            self._do_remove_schema(filepath)
        except Exception as exc:
            self.__publish_event(
                TripleStoreError(
                    operation="remove_schema",
                    filepath=filepath,
                    message=self._error_message(exc),
                )
            )
            raise

        self.__publish_event(SchemaRemoved(filepath=filepath))

    def _do_remove_schema(self, filepath: str):
        try:
            rows = list(
                self.query(
                    f'''
                    PREFIX internal: <http://triple-store.internal#>
                    SELECT ?s ?content
                    WHERE {{
                        GRAPH <{self.__schema_graph!s}> {{
                            ?s a internal:Schema ;
                               internal:filePath "{filepath}" ;
                               internal:content ?content .
                        }}
                    }}
                    '''
                )
            )

            if len(rows) == 0:
                logger.debug(f"No schema found in store for filepath: {filepath}")
                return

            schema_triples = Graph()
            metadata_triples = Graph()

            for row in rows:
                assert isinstance(row, rdflib.query.ResultRow)
                subject, content = row
                assert isinstance(subject, URIRef)

                # Rebuild schema triples from stored base64 content.
                decoded_content = base64.b64decode(str(content)).decode("utf-8")
                schema_graph = Graph().parse(
                    io.StringIO(decoded_content), format="turtle"
                )
                schema_triples += schema_graph

                metadata = self.query(
                    f"""
                    SELECT ?p ?o
                    WHERE {{
                        GRAPH <{self.__schema_graph!s}> {{
                            <{subject!s}> ?p ?o .
                        }}
                    }}
                    """
                )

                for metadata_row in metadata:
                    assert isinstance(metadata_row, rdflib.query.ResultRow)
                    predicate, obj = metadata_row
                    metadata_triples.add((subject, predicate, obj))

            if len(schema_triples) > 0:
                self.remove(schema_triples, graph_name=self.__schema_graph)

            if len(metadata_triples) > 0:
                self.remove(metadata_triples, graph_name=self.__schema_graph)
        except Exception as e:  # noqa: BLE001
            import traceback

            logger.error(f"Error removing schema ({filepath}): {e!s}")
            traceback.print_exc()

    def get_schema_graph(self) -> Graph:
        contents: rdflib.query.Result = self.query(
            f"""
            PREFIX internal: <http://triple-store.internal#>
            SELECT ?s ?o WHERE {{
                GRAPH <{self.__schema_graph!s}> {{
                    ?s internal:content ?o .
                }}
            }}
            """
        )

        graph = Graph()

        for row in contents:
            assert isinstance(row, rdflib.query.ResultRow)
            _, o = row

            g = Graph().parse(
                io.StringIO(base64.b64decode(o).decode("utf-8")), format="turtle"
            )

            graph += g

            for prefix, namespace in g.namespaces():
                graph.bind(prefix, namespace)

        return graph
