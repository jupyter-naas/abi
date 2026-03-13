from __future__ import annotations

import threading
from io import BytesIO
from pathlib import Path
from typing import Any, Tuple

import rdflib
from naas_abi_core.services.triple_store.TripleStorePorts import (
    Exceptions,
    ITripleStorePort,
    OntologyEvent,
)
from rdflib import Graph, URIRef
from rdflib.plugins.sparql.results.jsonresults import JSONResultParser


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

        triples_nt = triples.serialize(format="nt")
        delete_query = f"DELETE DATA {{ GRAPH <{self._graph_iri(graph_name)}> {{ {triples_nt} }} }}"
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
            CONSTRUCT {{ <{subject}> ?p ?o }}
            WHERE {{
                {{ <{subject}> ?p ?o }}
                UNION
                {{ GRAPH ?g {{ <{subject}> ?p ?o }} }}
            }}
            """
        else:
            query = f"""
            CONSTRUCT {{ <{subject}> ?p ?o }}
            WHERE {{ GRAPH <{graph_name}> {{ <{subject}> ?p ?o }} }}
            """

        result = self.query(query)
        assert isinstance(result, Graph)
        if len(result) == 0:
            raise Exceptions.SubjectNotFoundError(f"Subject {subject} not found")
        return result

    def query(self, query: str) -> Any:
        from pyoxigraph import (
            QueryBoolean,
            QueryResultsFormat,
            QuerySolutions,
            QueryTriples,
        )
        from pyoxigraph import RdfFormat

        with self._lock:
            result = self._store.query(query)

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

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.query(query)

    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
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
