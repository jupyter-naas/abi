import base64
import hashlib
import io
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, List

import rdflib
from naas_abi_core import logger
from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.triple_store.TripleStorePorts import (
    ITripleStorePort,
    ITripleStoreService,
    OntologyEvent,
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
    """

    def __init__(
        self,
        triple_store_adapter: ITripleStorePort,
    ):
        super().__init__()
        self.__triple_store_adapter = triple_store_adapter
        self.__schema_graph = URIRef("http://ontology.naas.ai/graph/schema")

        # Load SCHEMA_TTL in IOBuffer
        schema_ttl_buffer = io.StringIO(SCHEMA_TTL)
        self.insert(
            Graph().parse(schema_ttl_buffer, format="turtle"),
            graph_name=self.__schema_graph,
        )

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

        # Insert the triples into the store
        self.__triple_store_adapter.insert(triples, graph_name=graph_name)

        if self.services_wired is False:
            return

        # Notify listeners of the insert
        for s, p, o in triples.triples((None, None, None)):
            triple_bytes = f"{s.n3()} {p.n3()} {o.n3()} .\n".encode("utf-8")

            try:
                topic = f"ts.insert.g.{self._hash_value(str(graph_name))}.s.{self._hash_value(s)}.p.{self._hash_value(p)}.o.{self._hash_value(o)}"
                self.services.bus.publish(
                    "triple_store",
                    topic,
                    triple_bytes,
                )
            except Exception as e:
                logger.error(f"Error publishing triple: {e}")
                raise e

    def remove(
        self,
        triples: Graph,
        graph_name: URIRef,
    ) -> None:
        assert graph_name is not None

        # Remove the triples from the store
        self.__triple_store_adapter.remove(triples, graph_name=graph_name)

        if self.services_wired is False:
            return

        # Notify listeners of the delete
        for s, p, o in triples.triples((None, None, None)):
            triple_bytes = f"{s.n3()} {p.n3()} {o.n3()} .\n".encode("utf-8")

            try:
                topic = f"ts.delete.g.{self._hash_value(str(graph_name))}.s.{self._hash_value(s)}.p.{self._hash_value(p)}.o.{self._hash_value(o)}"
                self.services.bus.publish(
                    "triple_store",
                    topic,
                    triple_bytes,
                )
            except Exception as e:
                logger.error(f"Error publishing triple: {e}")
                raise e

    def get(self) -> Graph:
        return self.__triple_store_adapter.get()

    def query(self, query: str) -> rdflib.query.Result:
        return self.__triple_store_adapter.query(query)

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.__triple_store_adapter.query_view(view, query)

    def create_graph(self, graph_name: URIRef) -> None:
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)

        self.__triple_store_adapter.create_graph(graph_name)

    def clear_graph(self, graph_name: URIRef) -> None:
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)

        self.__triple_store_adapter.clear_graph(graph_name)

    def drop_graph(self, graph_name: URIRef) -> None:
        self.__triple_store_adapter.drop_graph(graph_name)

    def list_graphs(self) -> list[URIRef]:
        return self.__triple_store_adapter.list_graphs()

    def subscribe(
        self,
        topic: tuple[URIRef | None, URIRef | None, URIRef | None],
        callback: Callable[[bytes], None],
        event_type: OntologyEvent | None = None,
        graph_name: URIRef | str = "*",
    ) -> None:
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
                GRAPH <{str(self.__schema_graph)}> {{
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
                GRAPH <{str(self.__schema_graph)}> {{
                    <{str(subject)}> internal:content ?content .
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
                GRAPH <{str(self.__schema_graph)}> {{
                    <{str(subject)}> ?p ?o .
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

    def load_schemas(self, filepaths: List[str]):
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
                    self._apply_schema_for_file, filepath, index.get(filepath, [])
                )
                for filepath in filepaths
            ]
            for future in futures:
                future.result()

    def load_schema(self, filepath: str, schema_cache: Graph | None = None):
        """Single-file schema load. `schema_cache` is accepted for backward
        compatibility but ignored — we always look up via a filtered query."""
        del schema_cache  # legacy param, no longer used
        entries = self._build_schema_index(filepath_filter=filepath).get(filepath, [])
        self._apply_schema_for_file(filepath, entries)

    def _apply_schema_for_file(
        self, filepath: str, entries: List[_SchemaIndexEntry]
    ) -> None:
        try:
            if not entries:
                self._insert_new_schema(filepath)
                return

            with open(filepath, "r") as file:
                new_content = file.read()
            new_content_hash = hashlib.sha256(
                new_content.encode("utf-8")
            ).hexdigest()

            matching = next(
                (e for e in entries if e.hash == new_content_hash), None
            )
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
        except Exception as e:
            import traceback

            logger.error(f"Error loading schema ({filepath}): {str(e)}")
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
            rows = list(
                self.query(
                    f'''
                    PREFIX internal: <http://triple-store.internal#>
                    SELECT ?s ?content
                    WHERE {{
                        GRAPH <{str(self.__schema_graph)}> {{
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
                        GRAPH <{str(self.__schema_graph)}> {{
                            <{str(subject)}> ?p ?o .
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
        except Exception as e:
            import traceback

            logger.error(f"Error removing schema ({filepath}): {str(e)}")
            traceback.print_exc()

    def get_schema_graph(self) -> Graph:
        contents: rdflib.query.Result = self.query(
            f"""
            PREFIX internal: <http://triple-store.internal#>
            SELECT ?s ?o WHERE {{
                GRAPH <{str(self.__schema_graph)}> {{
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
