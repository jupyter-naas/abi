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


class Presentation(RDFEntity):
    """
    PowerPoint Presentation
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/powerpoint/Presentation'
    _property_uris: ClassVar[dict] = {'hasSlide': 'http://ontology.naas.ai/abi/powerpoint/hasSlide', 'isPresentationOf': 'http://ontology.naas.ai/abi/powerpoint/isPresentationOf'}

    # Object properties
    hasSlide: Optional[Slide] = Field(default=None)
    isPresentationOf: Optional[Any] = Field(default=None)

class Slide(RDFEntity):
    """
    Slide
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/powerpoint/Slide'
    _property_uris: ClassVar[dict] = {'hasShape': 'http://ontology.naas.ai/abi/powerpoint/hasShape', 'isSlideOf': 'http://ontology.naas.ai/abi/powerpoint/isSlideOf'}

    # Object properties
    hasShape: Optional[Shape] = Field(default=None)
    isSlideOf: Optional[Presentation] = Field(default=None)

class Shape(RDFEntity):
    """
    Shape
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/powerpoint/Shape'
    _property_uris: ClassVar[dict] = {'isShapeOf': 'http://ontology.naas.ai/abi/powerpoint/isShapeOf', 'shape_alt_text': 'http://ontology.naas.ai/abi/powerpoint/shape_alt_text', 'shape_id': 'http://ontology.naas.ai/abi/powerpoint/shape_id', 'shape_position_left': 'http://ontology.naas.ai/abi/powerpoint/shape_position_left', 'shape_position_top': 'http://ontology.naas.ai/abi/powerpoint/shape_position_top', 'shape_rotation_angle': 'http://ontology.naas.ai/abi/powerpoint/shape_rotation_angle', 'shape_size_height': 'http://ontology.naas.ai/abi/powerpoint/shape_size_height', 'shape_size_width': 'http://ontology.naas.ai/abi/powerpoint/shape_size_width', 'shape_text': 'http://ontology.naas.ai/abi/powerpoint/shape_text', 'shape_type': 'http://ontology.naas.ai/abi/powerpoint/shape_type'}

    # Data properties
    shape_alt_text: Optional[str] = Field(default=None)
    shape_id: Optional[int] = Field(default=None)
    shape_position_left: Optional[Any] = Field(default=None)
    shape_position_top: Optional[Any] = Field(default=None)
    shape_rotation_angle: Optional[Any] = Field(default=None)
    shape_size_height: Optional[Any] = Field(default=None)
    shape_size_width: Optional[Any] = Field(default=None)
    shape_text: Optional[str] = Field(default=None)
    shape_type: Optional[int] = Field(default=None)

    # Object properties
    isShapeOf: Optional[Slide] = Field(default=None)

# Rebuild models to resolve forward references
Presentation.model_rebuild()
Slide.model_rebuild()
Shape.model_rebuild()
