from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Any

import rdflib
from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    OntologyEvent,
    QueryDataset,
    QueryStream,
    Triple,
    iri_n3,
)
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.plugins.sparql.results.jsonresults import JSONResultParser
from rdflib.term import Node


class TripleStoreService__SecondaryAdaptor__OxigraphEmbedded(ITripleStorePort):
    _stores: dict[str, Any] = {}
    _stores_lock = threading.Lock()

    def __init__(
        self,
        store_path: str,
        graph_base_iri: str = "http://ontology.naas.ai/graph/default",
    ) -> None:
        try:
            from pyoxigraph import Store
        except ImportError as exc:
            raise ImportError(
                "oxigraph_embedded adapter requires pyoxigraph. "
                "Install with: uv pip install pyoxigraph"
            ) from exc

        with self._stores_lock:
            existing = self._stores.get(store_path)
            if existing is None:
                Path(store_path).mkdir(parents=True, exist_ok=True)
                existing = Store(path=store_path)
                self._stores[store_path] = existing

        self._store: Any = existing
        self._default_graph_iri = URIRef(graph_base_iri)
        self._lock = threading.RLock()

    def _graph_iri(self, graph_name: URIRef | None) -> URIRef:
        return self._default_graph_iri if graph_name is None else graph_name

    def _graph_node(self, graph_name: URIRef | None):
        from pyoxigraph import NamedNode

        return NamedNode(str(self._graph_iri(graph_name)))

    def insert(self, triples: Graph, graph_name: URIRef | None = None):
        if len(triples) == 0:
            return

        from pyoxigraph import RdfFormat

        with self._lock:
            self._store.load(
                input=triples.serialize(format="nt").encode("utf-8"),
                format=RdfFormat.N_TRIPLES,
                to_graph=self._graph_node(graph_name),
            )

    def remove(self, triples: Graph, graph_name: URIRef | None = None):
        if len(triples) == 0:
            return

        filtered = Graph()
        for s, p, o in triples:
            if not (
                isinstance(s, BNode) or isinstance(p, BNode) or isinstance(o, BNode)
            ):
                filtered.add((s, p, o))

        if len(filtered) == 0:
            return

        triples_nt = filtered.serialize(format="nt")
        delete_query = f"DELETE DATA {{ GRAPH {iri_n3(self._graph_iri(graph_name))} {{ {triples_nt} }} }}"
        with self._lock:
            self._store.update(delete_query)

    def get(self) -> Graph:
        query = """
        CONSTRUCT { ?s ?p ?o }
        WHERE {
            { ?s ?p ?o }
            UNION
            { GRAPH ?g { ?s ?p ?o } }
        }
        """
        result = self.query(query)
        assert isinstance(result, Graph)
        return result

    def get_subject_graph(self, subject: URIRef, graph_name: str | URIRef) -> Graph:
        if graph_name == "*":
            query = f"""
            CONSTRUCT {{ {iri_n3(subject)} ?p ?o }}
            WHERE {{
                {{ {iri_n3(subject)} ?p ?o }}
                UNION
                {{ GRAPH ?g {{ {iri_n3(subject)} ?p ?o }} }}
            }}
            """
        else:
            query = f"""
            CONSTRUCT {{ {iri_n3(subject)} ?p ?o }}
            WHERE {{ GRAPH {iri_n3(graph_name)} {{ {iri_n3(subject)} ?p ?o }} }}
            """

        result = self.query(query)
        assert isinstance(result, Graph)
        if len(result) == 0:
            raise Exceptions.SubjectNotFoundError(f"Subject {subject} not found")
        return result

    def query(self, query: str) -> Any:
        return self._query(query)

    def query_dataset(self, query: str, dataset: QueryDataset) -> Any:
        return self._query(query, **_dataset_options(dataset))

    def _query(self, query: str, **options: Any) -> Any:
        from pyoxigraph import (
            QueryBoolean,
            QueryResultsFormat,
            QuerySolutions,
            QueryTriples,
            RdfFormat,
        )

        with self._lock:
            result = self._store.query(query, **options)

        if isinstance(result, QueryTriples):
            serialized = result.serialize(format=RdfFormat.N_TRIPLES)
            if serialized is None:
                raise ValueError("Oxigraph returned no bytes for triple query result")
            return Graph().parse(
                data=serialized.decode("utf-8"),
                format="nt",
            )

        if isinstance(result, QuerySolutions):
            serialized = result.serialize(format=QueryResultsFormat.JSON)
            if serialized is None:
                raise ValueError("Oxigraph returned no bytes for solution query result")
            return JSONResultParser().parse(BytesIO(serialized))

        if isinstance(result, QueryBoolean):
            serialized = result.serialize(format=QueryResultsFormat.JSON)
            if serialized is None:
                raise ValueError("Oxigraph returned no bytes for boolean query result")
            return JSONResultParser().parse(BytesIO(serialized))

        raise ValueError(f"Unsupported query result type: {type(result)}")

    @contextmanager
    def query_stream(self, query: str) -> Iterator[QueryStream]:
        with self._query_stream(query) as result:
            yield result

    @contextmanager
    def query_stream_dataset(
        self, query: str, dataset: QueryDataset
    ) -> Iterator[QueryStream]:
        with self._query_stream(query, **_dataset_options(dataset)) as result:
            yield result

    @contextmanager
    def _query_stream(self, query: str, **options: Any) -> Iterator[QueryStream]:
        """Iterate pyoxigraph's lazy result.

        pyoxigraph results are bound to the thread that ran the query (another
        thread touching them aborts the process): open and read a stream on
        one thread.
        """
        from pyoxigraph import QueryBoolean, QuerySolutions, QueryTriples

        with self._lock:
            result = self._store.query(query, **options)
        if isinstance(result, QueryBoolean):
            yield QueryStream("ASK", ask_answer=bool(result))
        elif isinstance(result, QuerySolutions):
            names = [variable.value for variable in result.variables]
            yield QueryStream(
                "SELECT",
                vars=names,
                rows=(
                    {
                        name: _term(solution[name])
                        for name in names
                        if solution[name] is not None
                    }
                    for solution in result
                ),
            )
        elif isinstance(result, QueryTriples):
            yield QueryStream(
                "CONSTRUCT",
                triples=(
                    (_term(t.subject), _term(t.predicate), _term(t.object))
                    for t in result
                ),
            )
        else:  # an update: nothing to read
            yield QueryStream("SELECT")

    @contextmanager
    def export(self, graph_name: URIRef | None = None) -> Iterator[Iterator[Triple]]:
        """One named graph, or every graph as ``get()`` (a triple held in several
        graphs is then read once per graph)."""
        from pyoxigraph import NamedNode

        graph = NamedNode(str(graph_name)) if graph_name is not None else None
        with self._lock:
            quads = self._store.quads_for_pattern(None, None, None, graph)
        yield ((_term(q.subject), _term(q.predicate), _term(q.object)) for q in quads)

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.query(query)

    def handle_view_event(
        self,
        view: tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        return None

    def create_graph(self, graph_name: URIRef):
        with self._lock:
            if self._store.contains_named_graph(self._graph_node(graph_name)):
                raise Exceptions.GraphAlreadyExistsError(
                    f"Graph {graph_name} already exists"
                )
            self._store.add_graph(self._graph_node(graph_name))

    def clear_graph(self, graph_name: URIRef):
        with self._lock:
            if not self._store.contains_named_graph(self._graph_node(graph_name)):
                raise Exceptions.GraphNotFoundError(f"Graph {graph_name} not found")
            self._store.clear_graph(self._graph_node(graph_name))

    def drop_graph(self, graph_name: URIRef):
        with self._lock:
            if not self._store.contains_named_graph(self._graph_node(graph_name)):
                raise Exceptions.GraphNotFoundError(f"Graph {graph_name} not found")
            self._store.remove_graph(self._graph_node(graph_name))

    def list_graphs(self) -> list[URIRef]:
        with self._lock:
            return [URIRef(graph.value) for graph in self._store.named_graphs()]


def _term(node: Any) -> Node:
    """A pyoxigraph term as rdflib's (a plain string stays a plain Literal)."""
    from pyoxigraph import BlankNode, NamedNode

    if isinstance(node, NamedNode):
        return URIRef(node.value)
    if isinstance(node, BlankNode):
        return BNode(node.value)
    if node.language:
        return Literal(node.value, lang=node.language)
    datatype = node.datatype.value
    if datatype == str(XSD.string):
        return Literal(node.value)
    return Literal(node.value, datatype=URIRef(datatype))


def _dataset_options(dataset: QueryDataset) -> dict[str, Any]:
    """pyoxigraph's ``default_graph`` / ``named_graphs`` for ``dataset``."""
    from pyoxigraph import DefaultGraph, NamedNode

    default: list[Any] = [DefaultGraph()] if dataset.default_graph else []
    default += [NamedNode(str(graph)) for graph in dataset.default_graphs]
    return {
        "default_graph": default,
        "named_graphs": [NamedNode(str(graph)) for graph in dataset.named_graphs],
    }
