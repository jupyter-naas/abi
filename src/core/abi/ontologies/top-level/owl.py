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


class Thing(RDFEntity):
    """
    The class of OWL individuals.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#Thing'
    _property_uris: ClassVar[dict] = {'bottomDataProperty': 'http://www.w3.org/2002/07/owl#bottomDataProperty', 'bottomObjectProperty': 'http://www.w3.org/2002/07/owl#bottomObjectProperty', 'topDataProperty': 'http://www.w3.org/2002/07/owl#topDataProperty', 'topObjectProperty': 'http://www.w3.org/2002/07/owl#topObjectProperty'}

    # Data properties
    bottomDataProperty: Optional[Any] = Field(default=None)
    topDataProperty: Optional[Any] = Field(default=None)

    # Object properties
    bottomObjectProperty: Optional[Thing] = Field(default=None)
    topObjectProperty: Optional[Thing] = Field(default=None)

class AllDifferent(RDFEntity):
    """
    The class of collections of pairwise different individuals.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#AllDifferent'
    _property_uris: ClassVar[dict] = {}
    pass

class AllDisjointClasses(RDFEntity):
    """
    The class of collections of pairwise disjoint classes.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#AllDisjointClasses'
    _property_uris: ClassVar[dict] = {}
    pass

class AllDisjointProperties(RDFEntity):
    """
    The class of collections of pairwise disjoint properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#AllDisjointProperties'
    _property_uris: ClassVar[dict] = {}
    pass

class Annotation(RDFEntity):
    """
    The class of annotated annotations for which the RDF serialization consists of an annotated subject, predicate and object.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#Annotation'
    _property_uris: ClassVar[dict] = {}
    pass

class AnnotationProperty(RDFEntity):
    """
    The class of annotation properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#AnnotationProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class Axiom(RDFEntity):
    """
    The class of annotated axioms for which the RDF serialization consists of an annotated subject, predicate and object.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#Axiom'
    _property_uris: ClassVar[dict] = {}
    pass

class Class(RDFEntity):
    """
    The class of OWL classes.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#Class'
    _property_uris: ClassVar[dict] = {}
    pass

class DataRange(RDFEntity):
    """
    The class of OWL data ranges, which are special kinds of datatypes. Note: The use of the IRI owl:DataRange has been deprecated as of OWL 2. The IRI rdfs:Datatype SHOULD be used instead.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#DataRange'
    _property_uris: ClassVar[dict] = {}
    pass

class DatatypeProperty(RDFEntity):
    """
    The class of data properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#DatatypeProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class DeprecatedClass(RDFEntity):
    """
    The class of deprecated classes.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#DeprecatedClass'
    _property_uris: ClassVar[dict] = {}
    pass

class DeprecatedProperty(RDFEntity):
    """
    The class of deprecated properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#DeprecatedProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class FunctionalProperty(RDFEntity):
    """
    The class of functional properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#FunctionalProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class NegativePropertyAssertion(RDFEntity):
    """
    The class of negative property assertions.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#NegativePropertyAssertion'
    _property_uris: ClassVar[dict] = {}
    pass

class ObjectProperty(RDFEntity):
    """
    The class of object properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#ObjectProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class Ontology(RDFEntity):
    """
    The class of ontologies.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#Ontology'
    _property_uris: ClassVar[dict] = {}
    pass

class OntologyProperty(RDFEntity):
    """
    The class of ontology properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#OntologyProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class Nothing(Thing, RDFEntity):
    """
    This is the empty class.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#Nothing'
    _property_uris: ClassVar[dict] = {'bottomDataProperty': 'http://www.w3.org/2002/07/owl#bottomDataProperty', 'bottomObjectProperty': 'http://www.w3.org/2002/07/owl#bottomObjectProperty', 'topDataProperty': 'http://www.w3.org/2002/07/owl#topDataProperty', 'topObjectProperty': 'http://www.w3.org/2002/07/owl#topObjectProperty'}

    # Data properties
    bottomDataProperty: Optional[Any] = Field(default=None)
    topDataProperty: Optional[Any] = Field(default=None)

    # Object properties
    bottomObjectProperty: Optional[Thing] = Field(default=None)
    topObjectProperty: Optional[Thing] = Field(default=None)

class AsymmetricProperty(ObjectProperty, RDFEntity):
    """
    The class of asymmetric properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#AsymmetricProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class InverseFunctionalProperty(ObjectProperty, RDFEntity):
    """
    The class of inverse-functional properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#InverseFunctionalProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class IrreflexiveProperty(ObjectProperty, RDFEntity):
    """
    The class of irreflexive properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#IrreflexiveProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class NamedIndividual(Thing, RDFEntity):
    """
    The class of named individuals.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#NamedIndividual'
    _property_uris: ClassVar[dict] = {'bottomDataProperty': 'http://www.w3.org/2002/07/owl#bottomDataProperty', 'bottomObjectProperty': 'http://www.w3.org/2002/07/owl#bottomObjectProperty', 'topDataProperty': 'http://www.w3.org/2002/07/owl#topDataProperty', 'topObjectProperty': 'http://www.w3.org/2002/07/owl#topObjectProperty'}

    # Data properties
    bottomDataProperty: Optional[Any] = Field(default=None)
    topDataProperty: Optional[Any] = Field(default=None)

    # Object properties
    bottomObjectProperty: Optional[Thing] = Field(default=None)
    topObjectProperty: Optional[Thing] = Field(default=None)

class ReflexiveProperty(ObjectProperty, RDFEntity):
    """
    The class of reflexive properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#ReflexiveProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class Restriction(Class, RDFEntity):
    """
    The class of property restrictions.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#Restriction'
    _property_uris: ClassVar[dict] = {}
    pass

class SymmetricProperty(ObjectProperty, RDFEntity):
    """
    The class of symmetric properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#SymmetricProperty'
    _property_uris: ClassVar[dict] = {}
    pass

class TransitiveProperty(ObjectProperty, RDFEntity):
    """
    The class of transitive properties.
    """

    _class_uri: ClassVar[str] = 'http://www.w3.org/2002/07/owl#TransitiveProperty'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Thing.model_rebuild()
AllDifferent.model_rebuild()
AllDisjointClasses.model_rebuild()
AllDisjointProperties.model_rebuild()
Annotation.model_rebuild()
AnnotationProperty.model_rebuild()
Axiom.model_rebuild()
Class.model_rebuild()
DataRange.model_rebuild()
DatatypeProperty.model_rebuild()
DeprecatedClass.model_rebuild()
DeprecatedProperty.model_rebuild()
FunctionalProperty.model_rebuild()
NegativePropertyAssertion.model_rebuild()
ObjectProperty.model_rebuild()
Ontology.model_rebuild()
OntologyProperty.model_rebuild()
Nothing.model_rebuild()
AsymmetricProperty.model_rebuild()
InverseFunctionalProperty.model_rebuild()
IrreflexiveProperty.model_rebuild()
NamedIndividual.model_rebuild()
ReflexiveProperty.model_rebuild()
Restriction.model_rebuild()
SymmetricProperty.model_rebuild()
TransitiveProperty.model_rebuild()
