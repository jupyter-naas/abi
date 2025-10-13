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


class N9c0a1cae88d9401a9ddc7ed6bb77095cb2(RDFEntity):
    _class_uri: ClassVar[str] = 'n9c0a1cae88d9401a9ddc7ed6bb77095cb2'
    _property_uris: ClassVar[dict] = {}
    pass

class N9c0a1cae88d9401a9ddc7ed6bb77095cb1(RDFEntity):
    _class_uri: ClassVar[str] = 'n9c0a1cae88d9401a9ddc7ed6bb77095cb1'
    _property_uris: ClassVar[dict] = {}
    pass

class N9c0a1cae88d9401a9ddc7ed6bb77095cb5(RDFEntity):
    _class_uri: ClassVar[str] = 'n9c0a1cae88d9401a9ddc7ed6bb77095cb5'
    _property_uris: ClassVar[dict] = {'ont00001809': 'https://www.commoncoreontologies.org/ont00001809'}

    # Object properties
    ont00001809: Optional[Any] = Field(default=None)

class N9c0a1cae88d9401a9ddc7ed6bb77095cb9(RDFEntity):
    _class_uri: ClassVar[str] = 'n9c0a1cae88d9401a9ddc7ed6bb77095cb9'
    _property_uris: ClassVar[dict] = {}
    pass

class N9c0a1cae88d9401a9ddc7ed6bb77095cb8(RDFEntity):
    _class_uri: ClassVar[str] = 'n9c0a1cae88d9401a9ddc7ed6bb77095cb8'
    _property_uris: ClassVar[dict] = {}
    pass

class N9c0a1cae88d9401a9ddc7ed6bb77095cb12(RDFEntity):
    _class_uri: ClassVar[str] = 'n9c0a1cae88d9401a9ddc7ed6bb77095cb12'
    _property_uris: ClassVar[dict] = {}
    pass

class N9c0a1cae88d9401a9ddc7ed6bb77095cb15(RDFEntity):
    _class_uri: ClassVar[str] = 'n9c0a1cae88d9401a9ddc7ed6bb77095cb15'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
N9c0a1cae88d9401a9ddc7ed6bb77095cb2.model_rebuild()
N9c0a1cae88d9401a9ddc7ed6bb77095cb1.model_rebuild()
N9c0a1cae88d9401a9ddc7ed6bb77095cb5.model_rebuild()
N9c0a1cae88d9401a9ddc7ed6bb77095cb9.model_rebuild()
N9c0a1cae88d9401a9ddc7ed6bb77095cb8.model_rebuild()
N9c0a1cae88d9401a9ddc7ed6bb77095cb12.model_rebuild()
N9c0a1cae88d9401a9ddc7ed6bb77095cb15.model_rebuild()
