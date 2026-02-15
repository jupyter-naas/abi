from __future__ import annotations
from typing import Optional, Any, ClassVar
from pydantic import BaseModel, Field
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


class TaxCodesEntity(RDFEntity):
    """
    Base class for taxcodes entities
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/accountant/taxcodes#TaxCodesEntity'
    _property_uris: ClassVar[dict] = {'hasType': 'http://naas.ai/ontology/accountant/taxcodes#hasType', 'relatedTo': 'http://naas.ai/ontology/accountant/taxcodes#relatedTo'}

    # Object properties
    hasType: Optional[Any] = Field(default=None)
    relatedTo: Optional[TaxCodesEntity] = Field(default=None)

class TaxCodesProcess(RDFEntity):
    """
    Processes related to taxcodes
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/accountant/taxcodes#TaxCodesProcess'
    _property_uris: ClassVar[dict] = {}
    pass

class TaxCodesMetric(RDFEntity):
    """
    Metrics and measurements for taxcodes
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/accountant/taxcodes#TaxCodesMetric'
    _property_uris: ClassVar[dict] = {'hasValue': 'http://naas.ai/ontology/accountant/taxcodes#hasValue'}

    # Data properties
    hasValue: Optional[Any] = Field(default=None)

# Rebuild models to resolve forward references
TaxCodesEntity.model_rebuild()
TaxCodesProcess.model_rebuild()
TaxCodesMetric.model_rebuild()
