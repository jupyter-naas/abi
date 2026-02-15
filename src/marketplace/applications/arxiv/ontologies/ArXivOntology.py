from __future__ import annotations
from typing import Optional, ClassVar
from pydantic import BaseModel, Field
import datetime
import uuid
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF

# Generated classes from TTL file

# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""
    _namespace: ClassVar[str] = "http://example.org/instance/"
    _uri: str = ""
    
    model_config = {
        'arbitrary_types_allowed': True,
        'extra': 'forbid'
    }
    
    def __init__(self, **kwargs):
        uri = kwargs.pop('_uri', None)
        super().__init__(**kwargs)
        if uri is not None:
            self._uri = uri
        elif not self._uri:
            self._uri = f"{self._namespace}{uuid.uuid4()}"
    
    @classmethod
    def set_namespace(cls, namespace: str):
        """Set the namespace for generating URIs"""
        cls._namespace = namespace
        
    def rdf(self, subject_uri: str | None = None) -> Graph:
        """Generate RDF triples for this instance"""
        g = Graph()
        
        # Use stored URI or provided subject_uri
        if subject_uri is None:
            subject_uri = self._uri
        subject = URIRef(subject_uri)
        
        # Add class type
        if hasattr(self, '_class_uri'):
            g.add((subject, RDF.type, URIRef(self._class_uri)))
        
        # Add properties
        if hasattr(self, '_property_uris'):
            for prop_name, prop_uri in self._property_uris.items():
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, 'rdf'):
                                # Add triples from related object
                                g += item.rdf()
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, 'rdf'):
                        # Add triples from related object
                        g += prop_value.rdf()
                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))
                    else:
                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))
        
        return g


class ArXivPaper(RDFEntity):
    """
    ArXiv Paper
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ArXivPaper'
    _property_uris: ClassVar[dict] = {'abstract': 'http://ontology.naas.ai/abi/abstract', 'arxivId': 'http://ontology.naas.ai/abi/arxivId', 'hasAuthor': 'http://ontology.naas.ai/abi/hasAuthor', 'hasCategory': 'http://ontology.naas.ai/abi/hasCategory', 'publishedDate': 'http://ontology.naas.ai/abi/publishedDate'}

    # Data properties
    abstract: Optional[str] = Field(default=None)
    arxivId: Optional[str] = Field(default=None)
    publishedDate: Optional[datetime.datetime] = Field(default=None)

    # Object properties
    hasAuthor: Optional[ArXivAuthor] = Field(default=None)
    hasCategory: Optional[ArXivCategory] = Field(default=None)

class ArXivAuthor(RDFEntity):
    """
    ArXiv Author
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ArXivAuthor'
    _property_uris: ClassVar[dict] = {}
    pass

class ArXivCategory(RDFEntity):
    """
    ArXiv Category
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ArXivCategory'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
ArXivPaper.model_rebuild()
ArXivAuthor.model_rebuild()
ArXivCategory.model_rebuild()
