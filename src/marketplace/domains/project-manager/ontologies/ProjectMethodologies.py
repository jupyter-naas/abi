from __future__ import annotations
from typing import Optional, ClassVar
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


class Methodology(RDFEntity):
    """
    A systematic approach to managing projects
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/project-management/methodologies#Methodology'
    _property_uris: ClassVar[dict] = {'complexity': 'http://naas.ai/ontology/project-management/methodologies#complexity', 'hasPhase': 'http://naas.ai/ontology/project-management/methodologies#hasPhase', 'hasRole': 'http://naas.ai/ontology/project-management/methodologies#hasRole', 'teamSize': 'http://naas.ai/ontology/project-management/methodologies#teamSize', 'usesPractice': 'http://naas.ai/ontology/project-management/methodologies#usesPractice'}

    # Data properties
    complexity: Optional[str] = Field(default=None)
    teamSize: Optional[str] = Field(default=None)

    # Object properties
    hasPhase: Optional[Phase] = Field(default=None)
    hasRole: Optional[Role] = Field(default=None)
    usesPractice: Optional[Practice] = Field(default=None)

class Practice(RDFEntity):
    """
    A specific technique or activity in project management
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/project-management/methodologies#Practice'
    _property_uris: ClassVar[dict] = {'producesArtifact': 'http://naas.ai/ontology/project-management/methodologies#producesArtifact'}

    # Object properties
    producesArtifact: Optional[Artifact] = Field(default=None)

class Artifact(RDFEntity):
    """
    A deliverable or document produced during project execution
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/project-management/methodologies#Artifact'
    _property_uris: ClassVar[dict] = {}
    pass

class Role(RDFEntity):
    """
    A defined responsibility or position in a project
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/project-management/methodologies#Role'
    _property_uris: ClassVar[dict] = {}
    pass

class Phase(RDFEntity):
    """
    A distinct stage in the project lifecycle
    """

    _class_uri: ClassVar[str] = 'http://naas.ai/ontology/project-management/methodologies#Phase'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Methodology.model_rebuild()
Practice.model_rebuild()
Artifact.model_rebuild()
Role.model_rebuild()
Phase.model_rebuild()
