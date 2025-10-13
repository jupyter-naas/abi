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


class SalesProcessesEntity(RDFEntity):
    """
    Base class for salesprocesses entities
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/sales-development-representative/salesprocesses#SalesProcessesEntity'
    _property_uris: ClassVar[dict] = {'hasType': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#hasType', 'relatedTo': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#relatedTo'}

    # Object properties
    hasType: Optional[Any] = Field(default=None)
    relatedTo: Optional[SalesProcessesEntity] = Field(default=None)

class SalesProcessesProcess(RDFEntity):
    """
    Processes related to salesprocesses
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/sales-development-representative/salesprocesses#SalesProcessesProcess'
    _property_uris: ClassVar[dict] = {}
    pass

class SalesProcessesMetric(RDFEntity):
    """
    Metrics and measurements for salesprocesses
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/sales-development-representative/salesprocesses#SalesProcessesMetric'
    _property_uris: ClassVar[dict] = {'hasValue': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#hasValue'}

    # Data properties
    hasValue: Optional[Any] = Field(default=None)

class SalesStage(SalesProcessesEntity, RDFEntity):
    """
    Stages in the sales process
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/sales-development-representative/salesprocesses#SalesStage'
    _property_uris: ClassVar[dict] = {'hasConversionRate': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#hasConversionRate', 'hasType': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#hasType', 'relatedTo': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#relatedTo'}

    # Data properties
    hasConversionRate: Optional[Any] = Field(default=None)

    # Object properties
    hasType: Optional[Any] = Field(default=None)
    relatedTo: Optional[SalesProcessesEntity] = Field(default=None)

class QualificationFramework(SalesProcessesEntity, RDFEntity):
    """
    Lead qualification frameworks (BANT, MEDDIC, etc.)
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/sales-development-representative/salesprocesses#QualificationFramework'
    _property_uris: ClassVar[dict] = {'hasType': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#hasType', 'relatedTo': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#relatedTo', 'requiresCriteria': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#requiresCriteria'}

    # Object properties
    hasType: Optional[Any] = Field(default=None)
    relatedTo: Optional[SalesProcessesEntity] = Field(default=None)
    requiresCriteria: Optional[Any] = Field(default=None)

class ProspectingMethod(SalesProcessesEntity, RDFEntity):
    """
    Methods for prospecting and lead generation
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/sales-development-representative/salesprocesses#ProspectingMethod'
    _property_uris: ClassVar[dict] = {'hasType': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#hasType', 'relatedTo': 'http://naas.ai/ontology/sales-development-representative/salesprocesses#relatedTo'}

    # Object properties
    hasType: Optional[Any] = Field(default=None)
    relatedTo: Optional[SalesProcessesEntity] = Field(default=None)

# Rebuild models to resolve forward references
SalesProcessesEntity.model_rebuild()
SalesProcessesProcess.model_rebuild()
SalesProcessesMetric.model_rebuild()
SalesStage.model_rebuild()
QualificationFramework.model_rebuild()
ProspectingMethod.model_rebuild()
