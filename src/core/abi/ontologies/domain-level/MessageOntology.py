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


class N088d01c6e4f64c25be188c6b34c6645db1(RDFEntity):
    _class_uri: ClassVar[str] = 'n088d01c6e4f64c25be188c6b34c6645db1'
    _property_uris: ClassVar[dict] = {'receives': 'http://ontology.naas.ai/messaging#receives'}

    # Object properties
    receives: Optional[Message] = Field(default=None)

class N088d01c6e4f64c25be188c6b34c6645db5(RDFEntity):
    _class_uri: ClassVar[str] = 'n088d01c6e4f64c25be188c6b34c6645db5'
    _property_uris: ClassVar[dict] = {'transmits': 'http://ontology.naas.ai/messaging#transmits'}

    # Object properties
    transmits: Optional[Message] = Field(default=None)

class Message(RDFEntity):
    """
    message
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/messaging#Message'
    _property_uris: ClassVar[dict] = {'hasContentLength': 'http://ontology.naas.ai/messaging#hasContentLength', 'hasTextualRepresentation': 'http://ontology.naas.ai/messaging#hasTextualRepresentation'}

    # Data properties
    hasContentLength: Optional[Any] = Field(default=None)
    hasTextualRepresentation: Optional[str] = Field(default=None)

class MessageReceiverRole(RDFEntity):
    """
    message receiver role
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/messaging#MessageReceiverRole'
    _property_uris: ClassVar[dict] = {}
    pass

class MessageReceptionProcess(RDFEntity):
    """
    message reception process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/messaging#MessageReceptionProcess'
    _property_uris: ClassVar[dict] = {'hasMessageInput': 'http://ontology.naas.ai/messaging#hasMessageInput'}

    # Object properties
    hasMessageInput: Optional[Message] = Field(default=None)

class MessageSenderRole(RDFEntity):
    """
    message sender role
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/messaging#MessageSenderRole'
    _property_uris: ClassVar[dict] = {}
    pass

class MessageTransmissionProcess(RDFEntity):
    """
    message transmission process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/messaging#MessageTransmissionProcess'
    _property_uris: ClassVar[dict] = {'hasMessageOutput': 'http://ontology.naas.ai/messaging#hasMessageOutput'}

    # Object properties
    hasMessageOutput: Optional[Message] = Field(default=None)

class ResponseGenerationProcess(RDFEntity):
    """
    response generation process
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/messaging#ResponseGenerationProcess'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
N088d01c6e4f64c25be188c6b34c6645db1.model_rebuild()
N088d01c6e4f64c25be188c6b34c6645db5.model_rebuild()
Message.model_rebuild()
MessageReceiverRole.model_rebuild()
MessageReceptionProcess.model_rebuild()
MessageSenderRole.model_rebuild()
MessageTransmissionProcess.model_rebuild()
ResponseGenerationProcess.model_rebuild()
