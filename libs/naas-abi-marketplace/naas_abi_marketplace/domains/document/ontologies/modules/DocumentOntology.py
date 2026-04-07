from __future__ import annotations
from typing import Annotated, Any, ClassVar, List, Optional, Union
from pydantic import BaseModel, Field
import uuid
import datetime
import os
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")


# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""

    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"
    _uri: str = ""
    _object_properties: ClassVar[set[str]] = set()

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


class File(RDFEntity):
    """
    File
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/document/File"
    _name: ClassVar[str] = "File"
    _property_uris: ClassVar[dict] = {
        "accessed_time": "http://ontology.naas.ai/abi/document/accessed_time",
        "created": "http://purl.org/dc/terms/created",
        "created_time": "http://ontology.naas.ai/abi/document/created_time",
        "creator": "http://purl.org/dc/terms/creator",
        "embodies": "http://ontology.naas.ai/abi/document/embodies",
        "encoding": "http://ontology.naas.ai/abi/document/encoding",
        "file_name": "http://ontology.naas.ai/abi/document/name",
        "file_path": "http://ontology.naas.ai/abi/document/path",
        "file_size_bytes": "http://ontology.naas.ai/abi/document/file_size_bytes",
        "is_directory": "http://ontology.naas.ai/abi/document/is_directory",
        "is_file": "http://ontology.naas.ai/abi/document/is_file",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "mime_type": "http://ontology.naas.ai/abi/document/mime_type",
        "modified_time": "http://ontology.naas.ai/abi/document/modified_time",
        "permissions": "http://ontology.naas.ai/abi/document/permissions",
    }
    _object_properties: ClassVar[set[str]] = {"embodies"}

    # Data properties
    file_path: Optional[
        Annotated[str, Field(description="The path of the document.")]
    ] = "unknown"
    file_name: Optional[
        Annotated[str, Field(description="The name of the document.")]
    ] = "unknown"
    mime_type: Optional[
        Annotated[str, Field(description="The MIME type of the document.")]
    ] = "unknown"
    file_size_bytes: Optional[
        Annotated[int, Field(description="The size of the document in bytes.")]
    ]
    created_time: Optional[
        Annotated[
            datetime.datetime,
            Field(description="The created timestamp of the document."),
        ]
    ]
    modified_time: Optional[
        Annotated[
            datetime.datetime,
            Field(description="The last modified timestamp of the document."),
        ]
    ]
    accessed_time: Optional[
        Annotated[
            datetime.datetime,
            Field(description="The last accessed timestamp of the document."),
        ]
    ]
    is_file: Optional[
        Annotated[bool, Field(description="True if the path points to a file.")]
    ]
    is_directory: Optional[
        Annotated[bool, Field(description="True if the path points to a directory.")]
    ]
    permissions: Optional[
        Annotated[
            str,
            Field(
                description="The file permissions of the document in Unix-like notation."
            ),
        ]
    ] = "unknown"
    encoding: Optional[
        Annotated[
            str,
            Field(
                description="The detected character encoding of the document when applicable."
            ),
        ]
    ] = "unknown"
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    embodies: Optional[
        Annotated[
            List[Union[Document, URIRef, str]],
            Field(description="A file embodies a document."),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Document(RDFEntity):
    """
    Document
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/document/Document"
    _name: ClassVar[str] = "Document"
    _property_uris: ClassVar[dict] = {
        "author": "http://ontology.naas.ai/abi/document/author",
        "content": "http://ontology.naas.ai/abi/document/content",
        "created": "http://purl.org/dc/terms/created",
        "creation_date": "http://ontology.naas.ai/abi/document/creation_date",
        "creator": "http://purl.org/dc/terms/creator",
        "description": "http://ontology.naas.ai/abi/document/description",
        "isEmbodiedIn": "http://ontology.naas.ai/abi/document/isEmbodiedIn",
        "keywords": "http://ontology.naas.ai/abi/document/keywords",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "language": "http://ontology.naas.ai/abi/document/language",
        "md5": "http://ontology.naas.ai/abi/document/md5",
        "sha1": "http://ontology.naas.ai/abi/document/sha1",
        "sha256": "http://ontology.naas.ai/abi/document/sha256",
        "subject": "http://ontology.naas.ai/abi/document/subject",
        "title": "http://ontology.naas.ai/abi/document/title",
    }
    _object_properties: ClassVar[set[str]] = {"isEmbodiedIn"}

    # Data properties
    md5: Optional[
        Annotated[
            str, Field(description="The MD5 checksum (hex) of the document content.")
        ]
    ] = "unknown"
    sha1: Optional[
        Annotated[
            str, Field(description="The SHA-1 checksum (hex) of the document content.")
        ]
    ] = "unknown"
    sha256: Optional[
        Annotated[
            str,
            Field(description="The SHA-256 checksum (hex) of the document content."),
        ]
    ] = "unknown"
    content: Optional[
        Annotated[
            str,
            Field(
                description="The textual content of the document (when extracted or provided)."
            ),
        ]
    ] = "unknown"
    title: Optional[Annotated[str, Field(description="The title of the document.")]] = (
        "unknown"
    )
    author: Optional[
        Annotated[str, Field(description="The author of the document.")]
    ] = "unknown"
    language: Optional[
        Annotated[str, Field(description="The language of the document content.")]
    ] = "unknown"
    creation_date: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The creation date of the document (when available from document-level metadata)."
            ),
        ]
    ]
    subject: Optional[
        Annotated[str, Field(description="The subject of the document.")]
    ] = "unknown"
    description: Optional[
        Annotated[
            str, Field(description="A short description or abstract of the document.")
        ]
    ] = "unknown"
    keywords: Optional[
        Annotated[
            str,
            Field(
                description="Keywords associated with the document (typically a comma-separated list)."
            ),
        ]
    ] = "unknown"
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    isEmbodiedIn: Optional[
        Annotated[
            List[Union[File, URIRef, str]],
            Field(description="A document is embodied in a file."),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


# Rebuild models to resolve forward references
File.model_rebuild()
Document.model_rebuild()
