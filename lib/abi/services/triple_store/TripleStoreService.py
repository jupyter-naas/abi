from abi.services.triple_store.TripleStorePorts import (
    ITripleStoreService,
    ITripleStorePort,
    OntologyEvent,
)
from rdflib import Graph, RDF, URIRef
import rdflib
from typing import Callable, List, Tuple
import uuid
import pydash
import hashlib
import os
import io
import base64
from abi import logger


from abi.utils.Workers import WorkerPool, Job

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


class TripleStoreService(ITripleStoreService):
    """TripleStoreService provides CRUD operations and SPARQL querying capabilities for ontologies.

    This service acts as a facade for ontology storage and retrieval operations. It handles storing,
    retrieving, merging and querying of RDF ontologies while providing optional filtering of
    non-named individuals.

    Attributes:
        __ontology_adaptor (ITripleStorePort): The storage adapter implementation used for
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
        ontology_adaptor: ITripleStorePort,
        views: List[Tuple[URIRef | None, URIRef | None, URIRef | None]] = [
            (None, RDF.type, None)
        ],
        trigger_worker_pool_size: int = 10,
    ):
        self.__ontology_adaptor = ontology_adaptor
        self.__event_listeners = {}
        self.__views: List[Tuple[URIRef | None, URIRef | None, URIRef | None]] = views

        self.__trigger_worker_pool = WorkerPool(trigger_worker_pool_size)

        # Load SCHEMA_TTL in IOBuffer
        schema_ttl_buffer = io.StringIO(SCHEMA_TTL)
        self.insert(Graph().parse(schema_ttl_buffer, format="turtle"))

        self.init_views()

    def __del__(self):
        self.__trigger_worker_pool.shutdown()

    def init_views(self):
        for view in self.__views:
            self.subscribe(
                view,
                OntologyEvent.INSERT,
                lambda event, triple: self.__ontology_adaptor.handle_view_event(
                    view, event, triple
                ),
            )
            self.subscribe(
                view,
                OntologyEvent.DELETE,
                lambda event, triple: self.__ontology_adaptor.handle_view_event(
                    view, event, triple
                ),
            )

    def insert(self, triples: Graph):
        # Insert the triples into the store
        self.__ontology_adaptor.insert(triples)

        # Notify listeners of the insert
        for s, p, o in triples.triples((None, None, None)):
            for ss, sp, so in self.__event_listeners:
                if (
                    (ss is None or str(ss) == str(s))
                    and (sp is None or str(sp) == str(p))
                    and (so is None or str(so) == str(o))
                ):
                    if OntologyEvent.INSERT in self.__event_listeners[ss, sp, so]:
                        for _, callback, background in self.__event_listeners[
                            ss, sp, so
                        ][OntologyEvent.INSERT]:
                            if background:
                                self.__trigger_worker_pool.submit(
                                    Job(None, callback, OntologyEvent.INSERT, (s, p, o))
                                )
                            else:
                                callback(OntologyEvent.INSERT, (s, p, o))

    def remove(self, triples: Graph):
        # Remove the triples from the store
        self.__ontology_adaptor.remove(triples)

        # Notify listeners of the delete
        for s, p, o in triples.triples((None, None, None)):
            for ss, sp, so in self.__event_listeners:
                if (
                    (ss is None or str(ss) == str(s))
                    and (sp is None or str(sp) == str(p))
                    and (so is None or str(so) == str(o))
                ):
                    if OntologyEvent.DELETE in self.__event_listeners[ss, sp, so]:
                        for _, callback, background in self.__event_listeners[
                            ss, sp, so
                        ][OntologyEvent.DELETE]:
                            if background:
                                self.__trigger_worker_pool.submit(
                                    Job(None, callback, OntologyEvent.DELETE, (s, p, o))
                                )
                            else:
                                callback(OntologyEvent.DELETE, (s, p, o))

    def get(self) -> Graph:
        return self.__ontology_adaptor.get()

    def query(self, query: str) -> rdflib.query.Result:
        return self.__ontology_adaptor.query(query)

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.__ontology_adaptor.query_view(view, query)

    def subscribe(
        self,
        topic: tuple,
        event_type: OntologyEvent,
        callback: Callable[[OntologyEvent, Tuple[str, str, str]], None],
        background: bool = False,
    ) -> str:
        if topic not in self.__event_listeners:
            self.__event_listeners[topic] = {}
        if event_type not in self.__event_listeners[topic]:
            self.__event_listeners[topic][event_type] = []

        subscription_id = str(uuid.uuid4())

        self.__event_listeners[topic][event_type].append(
            (subscription_id, callback, background)
        )

        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        for topic in self.__event_listeners:
            for event_type in self.__event_listeners[topic]:
                self.__event_listeners[topic][event_type] = pydash.filter_(
                    self.__event_listeners[topic][event_type],
                    lambda x: x[0] != subscription_id,
                )

    def get_subject_graph(self, subject: str) -> Graph:
        return self.__ontology_adaptor.get_subject_graph(URIRef(subject))

    ###################lib/abi/services/ontology/OntologyService.py#########################################
    # Schema Management
    ############################################################

    def load_schemas(self, filepaths: List[str]):
        # First build a cache of all schemas to speed up the process.
        schema_cache = Graph()
        
        results = self.query("""
            PREFIX internal: <http://triple-store.internal#>
            SELECT ?schema ?filePath ?hash ?fileLastUpdateTime ?content
            WHERE {
                ?schema a internal:Schema ;
                    internal:filePath ?filePath ;
                    internal:hash ?hash ;
                    internal:fileLastUpdateTime ?fileLastUpdateTime ;
                    internal:content ?content .
            }
        """)
        
        for row in results:
            assert isinstance(row, rdflib.query.ResultRow)
            schema, filePath, hash, fileLastUpdateTime, content = row
            schema_cache.add((schema, RDF.type, URIRef("http://triple-store.internal#Schema")))
            schema_cache.add((schema, URIRef("http://triple-store.internal#filePath"), filePath))
            schema_cache.add((schema, URIRef("http://triple-store.internal#hash"), hash))
            schema_cache.add((schema, URIRef("http://triple-store.internal#fileLastUpdateTime"), fileLastUpdateTime))
            schema_cache.add((schema, URIRef("http://triple-store.internal#content"), content))
        
        for filepath in filepaths:
            self.load_schema(filepath, schema_cache)


    def load_schema(self, filepath: str, schema_cache: Graph | None = None):
        logger.debug(f"Loading schema: {filepath}")
        if schema_cache is not None:
            def _read_query_func(query: str):
                return schema_cache.query(query)
            read_query_func = _read_query_func
        else:
            read_query_func = self.query

        try:

            query = f'''PREFIX internal: <http://triple-store.internal#>
            SELECT * WHERE {{ ?s internal:filePath "{filepath}" . }}'''
            # logger.debug(f"Query: {query}")
            # Check if schema with filePath == filepath already exists and grab all triples.
            schema_triples: rdflib.query.Result = read_query_func(query)

            # logger.debug(f"len(list(schema_triples)): {len(list(schema_triples))}")
            # If schema with filePath == filepath already exists, we check if the file has been modified.
            schema_exists_in_store = len(list(schema_triples)) == 1
            logger.debug(f"Schema exists in store: {schema_exists_in_store}")
            if schema_exists_in_store:
                result_rows = list(schema_triples)
                assert len(result_rows) == 1
                assert isinstance(result_rows[0], rdflib.query.ResultRow)
                _SUBJECT_TUPLE_INDEX = 0
                subject = result_rows[0][_SUBJECT_TUPLE_INDEX]

                # Select * from subject
                triples: rdflib.query.Result = read_query_func(
                        f"""PREFIX internal: <http://triple-store.internal#>
                        SELECT ?p ?o WHERE {{ <{subject}> ?p ?o . }}"""
                    )

                # Load schema into a dict
                schema_dict = {}
                for row in triples:
                    assert isinstance(row, rdflib.query.ResultRow)
                    p, o = row

                    schema_dict[str(p).replace("http://triple-store.internal#", "")] = str(
                        o
                    )

                # Get file last update time
                file_last_update_time = os.path.getmtime(filepath)

                # Open file and get content.
                with open(filepath, "r") as file:
                    new_content = file.read()

                new_content_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

                # If fileLastUpdateTime is the same, return. Otherwise we continue as we need to update the schema.
                if schema_dict["hash"] == new_content_hash:
                    logger.debug("Schema is up to date, no need to update.")
                    return

                logger.debug("Schema is not up to date, updating.")

                # Decode old content
                old_content = base64.b64decode(schema_dict["content"]).decode("utf-8")

                # Parse old and new schema
                old_schema = Graph().parse(io.StringIO(old_content), format="turtle")

                new_schema = Graph().parse(io.StringIO(new_content), format="turtle")

                # Compute addition and deletion triples
                addition_triples = new_schema - old_schema
                deletion_triples = old_schema - new_schema

                # Insert addition and remove deletion triples
                self.insert(addition_triples)
                self.remove(deletion_triples)

                # Update schema information in the triple store.

                self.remove(
                    Graph().parse(
                        io.StringIO(f'''
                    @prefix internal: <http://triple-store.internal#> .
                    
                    <{subject}> internal:hash "{schema_dict["hash"]}" ;
                        internal:fileLastUpdateTime "{schema_dict["fileLastUpdateTime"]}" ;
                        internal:content "{schema_dict["content"]}" .
                '''),
                        format="turtle",
                    )
                )

                self.insert(
                    Graph().parse(
                        io.StringIO(f'''
                    @prefix internal: <http://triple-store.internal#> .
                    
                    <{subject}> internal:hash "{new_content_hash}" ;
                        internal:fileLastUpdateTime "{file_last_update_time}" ;
                        internal:content "{base64.b64encode(new_content.encode("utf-8")).decode("utf-8")}" .
                '''),
                        format="turtle",
                    )
                )

                # Return as we don't need to continue as we have already updated the schema.
                return
            elif not schema_exists_in_store:
                logger.debug("Loading schema in graph as it doesn't exist in store.")

                # Open file and get content.
                with open(filepath, "r") as file:
                    content = file.read()

                # Compute base64 content
                base64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

                # Compute hash of content
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # Parse schema
                g = Graph().parse(filepath)

                # Insert schema into the triple store
                self.insert(g)

                # Get file last update time
                file_last_update_time = os.path.getmtime(filepath)

                # Insert Schema with hash, filePath, fileLastUpdateTime and content to be able to track changes.
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
                    )
                )
        except Exception as e:
            logger.error(f"Error loading schema ({filepath}): {e}")

    def get_schema_graph(self) -> Graph:
        contents: rdflib.query.Result = self.query(
            """PREFIX internal: <http://triple-store.internal#>
            SELECT ?s ?o WHERE { ?s internal:content ?o . }"""
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
