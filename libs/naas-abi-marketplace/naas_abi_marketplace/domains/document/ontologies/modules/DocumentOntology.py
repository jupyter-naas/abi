# onto2py-source-sha256: 3b61c1ee977d6c0c95d7d7aae885864bfb3075fd0fc67bdf9f07e467e6a9d015
from __future__ import annotations

import datetime
import uuid
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Iterable,
    List,
    Optional,
    Union,
    get_args,
    get_origin,
)

from naas_abi_core.modules.bfo.ontologies.modules import (
    Continuant,
    GenericallyDependentContinuant,
    TemporalRegion,
)
from pydantic import BaseModel, Field, ValidationError
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")


# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""

    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"
    _uri: str = ""
    _object_properties: ClassVar[set[str]] = set()
    _query_executor: ClassVar[Callable[[str], Iterable[object]] | None] = None

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}

    def __init__(self, **kwargs):
        uri = kwargs.pop("_uri", None)
        super().__init__(**kwargs)
        if uri is not None:
            self._uri = uri
        elif not self._uri:
            self._uri = f"{self._namespace}{uuid.uuid4()}"

    @classmethod
    def set_namespace(cls, namespace: str):
        """Set the namespace for generating URIs"""
        cls._namespace = namespace

    @classmethod
    def set_query_executor(
        cls, query_executor: Callable[[str], Iterable[object]] | None
    ):
        """Set the SPARQL query executor used by from_iri()."""
        cls._query_executor = query_executor

    @staticmethod
    def _extract_result_value(row: object, key: str) -> object | None:
        """Extract a SPARQL binding value from a ResultRow-like object."""
        if hasattr(row, key):
            return getattr(row, key)
        try:
            return row[key]  # type: ignore[index]
        except Exception:
            pass

        labels = getattr(row, "labels", None)
        if labels and key in labels:
            try:
                return row[key]  # type: ignore[index]
            except Exception:
                pass

        if isinstance(row, (list, tuple)):
            idx = 0 if key == "p" else 1
            if len(row) > idx:
                return row[idx]

        return None

    @staticmethod
    def _coerce_rdf_value(value: object, is_object_property: bool) -> object:
        """Convert RDFLib values to python values used by generated models."""
        if value is None:
            return None
        if is_object_property:
            return str(value)
        if isinstance(value, Literal):
            return value.toPython()
        return str(value)

    @staticmethod
    def _field_expects_list(field_annotation: object) -> bool:
        """Return True when a field annotation contains a list type."""
        origin = get_origin(field_annotation)
        if origin in (list, List):
            return True
        if origin is Annotated:
            args = get_args(field_annotation)
            if args:
                return RDFEntity._field_expects_list(args[0])
            return False
        if origin is Union:
            return any(
                RDFEntity._field_expects_list(arg)
                for arg in get_args(field_annotation)
                if arg is not type(None)
            )
        return False

    @staticmethod
    def _fallback_label_from_iri(iri: str) -> str:
        """Build a best-effort label from an IRI."""
        trimmed = iri.rstrip("/")
        if "#" in trimmed:
            return trimmed.split("#")[-1] or trimmed
        return trimmed.split("/")[-1] or trimmed

    @classmethod
    def from_iri(
        cls,
        iri: str,
        query_executor: Callable[[str], Iterable[object]] | None = None,
        graph_name: str | None = None,
    ):
        """Load a class instance from an IRI using SPARQL query results."""
        iri = str(iri).strip()
        if not iri:
            raise ValueError("iri must be a non-empty string")
        if "<" in iri or ">" in iri:
            raise ValueError("iri must not contain angle brackets")
        if graph_name is not None:
            graph_name = str(graph_name).strip()
            if not graph_name:
                graph_name = None
            elif "<" in graph_name or ">" in graph_name:
                raise ValueError("graph_name must not contain angle brackets")

        executor = query_executor or cls._query_executor
        if executor is None:
            raise ValueError(
                "No query executor configured. Pass query_executor to from_iri() "
                "or set it with set_query_executor()."
            )

        if graph_name:
            sparql_query = f"""
                SELECT ?p ?o
                WHERE {{
                    GRAPH <{graph_name}> {{
                        <{iri}> ?p ?o .
                        FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
                    }}
                }}
            """
        else:
            sparql_query = f"""
                SELECT ?p ?o
                WHERE {{
                    <{iri}> ?p ?o .
                    FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
                }}
            """

        results = executor(sparql_query)
        reverse_property_uris = {
            prop_uri: prop_name
            for prop_name, prop_uri in getattr(cls, "_property_uris", {}).items()
        }
        object_props: set[str] = getattr(cls, "_object_properties", set())
        model_fields = getattr(cls, "model_fields", {})
        values: dict[str, Any] = {}

        for row in results:  # type: ignore[assignment]
            predicate = cls._extract_result_value(row, "p")
            obj = cls._extract_result_value(row, "o")
            if predicate is None:
                continue
            prop_name = reverse_property_uris.get(str(predicate))
            if not prop_name:
                continue

            coerced = cls._coerce_rdf_value(
                obj,
                is_object_property=prop_name in object_props,
            )
            field_info = model_fields.get(prop_name)
            expects_list = False
            if field_info is not None:
                expects_list = cls._field_expects_list(field_info.annotation)

            if prop_name not in values:
                if expects_list:
                    values[prop_name] = [coerced]
                else:
                    values[prop_name] = coerced
            else:
                existing = values[prop_name]
                if isinstance(existing, list):
                    existing.append(coerced)
                elif expects_list:
                    values[prop_name] = [existing, coerced]
                else:
                    values[prop_name] = existing

        if "label" in model_fields and "label" not in values:
            values["label"] = cls._fallback_label_from_iri(iri)

        for field_name, field_info in model_fields.items():
            if field_name in values:
                continue
            if field_info.is_required():
                if cls._field_expects_list(field_info.annotation):
                    values[field_name] = []
                else:
                    values[field_name] = None

        try:
            return cls(_uri=iri, **values)
        except ValidationError:
            # Keep loading permissive for partially populated RDF resources.
            return cls.model_construct(
                _fields_set=set(values.keys()), _uri=iri, **values
            )

    def rdf(
        self, subject_uri: str | None = None, visited: set[str] | None = None
    ) -> Graph:
        """Generate RDF triples for this instance

        Args:
            subject_uri: Optional URI to use as subject (defaults to self._uri)
            visited: Set of URIs that have already been processed (for cycle detection)
        """
        # Initialize visited set if not provided
        if visited is None:
            visited = set()

        g = Graph()
        g.bind("cco", CCO)
        g.bind("bfo", BFO)
        g.bind("abi", ABI)
        g.bind("rdfs", RDFS)
        g.bind("rdf", RDF)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        # Use stored URI or provided subject_uri
        if subject_uri is None:
            subject_uri = self._uri
        subject = URIRef(subject_uri)

        # Check if we've already processed this entity (cycle detection)
        if subject_uri in visited:
            # Already processed, just return empty graph to avoid infinite recursion
            # The relationship triple will be added by the caller
            return g

        # Mark this entity as visited before processing
        visited.add(subject_uri)

        # Add class type
        if hasattr(self, "_class_uri"):
            g.add((subject, RDF.type, URIRef(self._class_uri)))

        # Add owl:NamedIndividual type
        g.add((subject, RDF.type, OWL.NamedIndividual))

        # Add label if it exists
        if hasattr(self, "label"):
            g.add((subject, RDFS.label, Literal(self.label)))

        object_props: set[str] = getattr(self, "_object_properties", set())

        # Add properties
        if hasattr(self, "_property_uris"):
            for prop_name, prop_uri in self._property_uris.items():
                is_object_prop = prop_name in object_props
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, "rdf") and hasattr(item, "_uri"):
                                # Check if this entity was already visited to prevent cycles
                                if item._uri not in visited:
                                    # Add triples from related object
                                    g += item.rdf(visited=visited)
                                # Always add the triple, even if already visited
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            elif is_object_prop and isinstance(item, (str, URIRef)):
                                g.add((subject, URIRef(prop_uri), URIRef(str(item))))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, "rdf") and hasattr(prop_value, "_uri"):
                        # Check if this entity was already visited to prevent cycles
                        if prop_value._uri not in visited:
                            # Add triples from related object
                            g += prop_value.rdf(visited=visited)
                        # Always add the triple, even if already visited
                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))
                    elif is_object_prop and isinstance(prop_value, (str, URIRef)):
                        g.add((subject, URIRef(prop_uri), URIRef(str(prop_value))))
                    else:
                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))

        return g


class File(GenericallyDependentContinuant, RDFEntity):
    """
    File
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/document/File"
    _name: ClassVar[str] = "File"
    _property_uris: ClassVar[dict] = {
        "accessed_time": "http://ontology.naas.ai/abi/document/accessed_time",
        "continuant_part_of": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "created_time": "http://ontology.naas.ai/abi/document/created_time",
        "creator": "http://purl.org/dc/terms/creator",
        "derivedFrom": "http://ontology.naas.ai/abi/document/derivedFrom",
        "embodies": "http://ontology.naas.ai/abi/document/embodies",
        "encoding": "http://ontology.naas.ai/abi/document/encoding",
        "exists_at": "http://purl.obolibrary.org/obo/BFO_0000108",
        "file_name": "http://ontology.naas.ai/abi/document/name",
        "file_path": "http://ontology.naas.ai/abi/document/path",
        "file_size_bytes": "http://ontology.naas.ai/abi/document/file_size_bytes",
        "generically_depends_on": "http://purl.obolibrary.org/obo/BFO_0000084",
        "hasChunk": "http://ontology.naas.ai/abi/document/hasChunk",
        "has_continuant_part": "http://purl.obolibrary.org/obo/BFO_0000178",
        "is_concretized_by": "http://purl.obolibrary.org/obo/BFO_0000058",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "mime_type": "http://ontology.naas.ai/abi/document/mime_type",
        "modified_time": "http://ontology.naas.ai/abi/document/modified_time",
        "permissions": "http://ontology.naas.ai/abi/document/permissions",
        "processedBy": "http://ontology.naas.ai/abi/document/processedBy",
        "sha256": "http://ontology.naas.ai/abi/document/sha256",
    }
    _object_properties: ClassVar[set[str]] = {
        "continuant_part_of",
        "derivedFrom",
        "embodies",
        "exists_at",
        "generically_depends_on",
        "hasChunk",
        "has_continuant_part",
        "is_concretized_by",
        "processedBy",
    }

    # Data properties
    file_path: Optional[
        Annotated[str, Field(description="The path of the document.")]
    ] = None
    file_name: Optional[
        Annotated[str, Field(description="The name of the document.")]
    ] = None
    mime_type: Optional[
        Annotated[str, Field(description="The MIME type of the document.")]
    ] = None
    file_size_bytes: Optional[
        Annotated[int, Field(description="The size of the document in bytes.")]
    ] = None
    created_time: Optional[
        Annotated[
            datetime.datetime,
            Field(description="The created timestamp of the document."),
        ]
    ] = None
    modified_time: Optional[
        Annotated[
            datetime.datetime,
            Field(description="The last modified timestamp of the document."),
        ]
    ] = None
    accessed_time: Optional[
        Annotated[
            datetime.datetime,
            Field(description="The last accessed timestamp of the document."),
        ]
    ] = None
    permissions: Optional[
        Annotated[
            str,
            Field(
                description="The file permissions of the document in Unix-like notation."
            ),
        ]
    ] = None
    encoding: Optional[
        Annotated[
            str,
            Field(
                description="The detected character encoding of the document when applicable."
            ),
        ]
    ] = None
    sha256: Optional[
        Annotated[
            str,
            Field(description="The SHA-256 checksum (hex) of the document content."),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    continuant_part_of: Optional[
        Annotated[
            List[Union[Continuant, URIRef, str]],
            Field(
                description="b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t"
            ),
        ]
    ] = None
    derivedFrom: Optional[
        Annotated[
            List[Union[File, URIRef, str]],
            Field(description="A file is derived from another file."),
        ]
    ] = None
    embodies: Optional[
        Annotated[
            List[Union[Document, URIRef, str]],
            Field(description="A file embodies a document."),
        ]
    ] = None
    exists_at: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="(Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists"
            ),
        ]
    ] = None
    generically_depends_on: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    hasChunk: Optional[
        Annotated[
            List[Union[Chunk, URIRef, str]],
            Field(description="A file has one or more chunks."),
        ]
    ] = None
    has_continuant_part: Optional[
        Annotated[
            List[Union[Continuant, URIRef, str]],
            Field(description="b has continuant part c =Def c continuant part of b"),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            Union[URIRef, str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    processedBy: Optional[
        Annotated[
            List[Union[Processor, URIRef, str]],
            Field(description="A file is processed by a processor."),
        ]
    ] = None


class Document(GenericallyDependentContinuant, RDFEntity):
    """
    Document
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/document/Document"
    _name: ClassVar[str] = "Document"
    _property_uris: ClassVar[dict] = {
        "continuant_part_of": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "exists_at": "http://purl.obolibrary.org/obo/BFO_0000108",
        "generically_depends_on": "http://purl.obolibrary.org/obo/BFO_0000084",
        "has_continuant_part": "http://purl.obolibrary.org/obo/BFO_0000178",
        "isEmbodiedIn": "http://ontology.naas.ai/abi/document/isEmbodiedIn",
        "is_concretized_by": "http://purl.obolibrary.org/obo/BFO_0000058",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "sha256": "http://ontology.naas.ai/abi/document/sha256",
    }
    _object_properties: ClassVar[set[str]] = {
        "continuant_part_of",
        "exists_at",
        "generically_depends_on",
        "has_continuant_part",
        "isEmbodiedIn",
        "is_concretized_by",
    }

    # Data properties
    sha256: Optional[
        Annotated[
            str,
            Field(description="The SHA-256 checksum (hex) of the document content."),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    continuant_part_of: Optional[
        Annotated[
            List[Union[Continuant, URIRef, str]],
            Field(
                description="b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t"
            ),
        ]
    ] = None
    exists_at: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="(Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists"
            ),
        ]
    ] = None
    generically_depends_on: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_continuant_part: Optional[
        Annotated[
            List[Union[Continuant, URIRef, str]],
            Field(description="b has continuant part c =Def c continuant part of b"),
        ]
    ] = None
    isEmbodiedIn: Optional[
        Annotated[
            List[Union[File, URIRef, str]],
            Field(description="A document is embodied in a file."),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            Union[URIRef, str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class Processor(GenericallyDependentContinuant, RDFEntity):
    """
    Processor
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/document/Processor"
    _name: ClassVar[str] = "Processor"
    _property_uris: ClassVar[dict] = {
        "continuant_part_of": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "exists_at": "http://purl.obolibrary.org/obo/BFO_0000108",
        "generically_depends_on": "http://purl.obolibrary.org/obo/BFO_0000084",
        "has_continuant_part": "http://purl.obolibrary.org/obo/BFO_0000178",
        "is_concretized_by": "http://purl.obolibrary.org/obo/BFO_0000058",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "continuant_part_of",
        "exists_at",
        "generically_depends_on",
        "has_continuant_part",
        "is_concretized_by",
    }

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    continuant_part_of: Optional[
        Annotated[
            List[Union[Continuant, URIRef, str]],
            Field(
                description="b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t"
            ),
        ]
    ] = None
    exists_at: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="(Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists"
            ),
        ]
    ] = None
    generically_depends_on: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_continuant_part: Optional[
        Annotated[
            List[Union[Continuant, URIRef, str]],
            Field(description="b has continuant part c =Def c continuant part of b"),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            Union[URIRef, str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class Chunk(GenericallyDependentContinuant, RDFEntity):
    """
    File
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/document/File"
    _name: ClassVar[str] = "File"
    _property_uris: ClassVar[dict] = {
        "chunk_file_path": "http://ontology.naas.ai/abi/document/file_path",
        "chunk_index": "http://ontology.naas.ai/abi/document/chunk_index",
        "collection_name": "http://ontology.naas.ai/abi/document/collection_name",
        "content": "http://ontology.naas.ai/abi/document/content",
        "continuant_part_of": "http://purl.obolibrary.org/obo/BFO_0000176",
        "created": "http://purl.org/dc/terms/created",
        "created_time": "http://ontology.naas.ai/abi/document/created_time",
        "creator": "http://purl.org/dc/terms/creator",
        "embedding_id": "http://ontology.naas.ai/abi/document/embedding_id",
        "exists_at": "http://purl.obolibrary.org/obo/BFO_0000108",
        "generically_depends_on": "http://purl.obolibrary.org/obo/BFO_0000084",
        "has_continuant_part": "http://purl.obolibrary.org/obo/BFO_0000178",
        "isChunkOf": "http://ontology.naas.ai/abi/document/isChunkOf",
        "is_concretized_by": "http://purl.obolibrary.org/obo/BFO_0000058",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "mime_type": "http://ontology.naas.ai/abi/document/mime_type",
        "modified_time": "http://ontology.naas.ai/abi/document/modified_time",
        "permissions": "http://ontology.naas.ai/abi/document/permissions",
        "processedBy": "http://ontology.naas.ai/abi/document/processedBy",
        "sha256": "http://ontology.naas.ai/abi/document/sha256",
    }
    _object_properties: ClassVar[set[str]] = {
        "derivedFrom",
        "embodies",
        "hasChunk",
        "processedBy",
    }
    _object_properties: ClassVar[set[str]] = {
        "continuant_part_of",
        "exists_at",
        "generically_depends_on",
        "has_continuant_part",
        "isChunkOf",
        "is_concretized_by",
    }

    # Data properties
    content: Optional[
        Annotated[str, Field(description="The text content of a chunk.")]
    ] = None
    chunk_index: Optional[
        Annotated[
            int,
            Field(
                description="The zero-based position of the chunk within its source document."
            ),
        ]
    ] = None
    embedding_id: Optional[
        Annotated[
            str,
            Field(
                description="The identifier of the vector embedding stored in the vector store."
            ),
        ]
    ] = None
    chunk_file_path: Optional[
        Annotated[
            str,
            Field(
                description="The detected character encoding of the document when applicable."
            ),
        ]
    ] = None
    sha256: Optional[
        Annotated[
            str,
            Field(description="The SHA-256 checksum (hex) of the document content."),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    continuant_part_of: Optional[
        Annotated[
            List[Union[Continuant, URIRef, str]],
            Field(
                description="b continuant part of c =Def b and c are continuants & there is some time t such that b and c exist at t & b continuant part of c at t"
            ),
        ]
    ] = None
    exists_at: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="(Elucidation) exists at is a relation between a particular and some temporal region at which the particular exists"
            ),
        ]
    ] = None
    generically_depends_on: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_continuant_part: Optional[
        Annotated[
            List[Union[Continuant, URIRef, str]],
            Field(description="b has continuant part c =Def c continuant part of b"),
        ]
    ] = None
    isChunkOf: Optional[
        Annotated[
            List[Union[File, URIRef, str]],
            Field(description="A file is derived from another file."),
        ]
    ] = None
    embodies: Optional[
        Annotated[
            List[Union[Document, URIRef, str]],
            Field(description="A file embodies a document."),
        ]
    ] = None
    hasChunk: Optional[
        Annotated[
            List[Union[Chunk, URIRef, str]],
            Field(description="A file has one or more chunks."),
        ]
    ] = None
    processedBy: Optional[
        Annotated[
            List[Union[Processor, URIRef, str]],
            Field(description="A file is processed by a processor."),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            Union[URIRef, str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


# Rebuild models to resolve forward references
File.model_rebuild()
Document.model_rebuild()
Processor.model_rebuild()
Chunk.model_rebuild()
