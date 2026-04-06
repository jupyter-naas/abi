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


class Offering(RDFEntity):
    """
    Offering
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Offering'
    _property_uris: ClassVar[dict] = {'isOfferingOf': 'http://ontology.naas.ai/abi/isOfferingOf', 'market_share': 'http://ontology.naas.ai/abi/market_share', 'targets': 'http://ontology.naas.ai/abi/Targets'}

    # Data properties
    market_share: Optional[Any] = Field(default=None)

    # Object properties
    isOfferingOf: Optional[Any] = Field(default=None)
    targets: Optional[Market] = Field(default=None)

class Market(RDFEntity):
    """
    A market is an abstract concept used to describe the environment in which trade occurs. As such, it is best represented as a Descriptive Information Content Entity that encompasses the characteristics and dynamics of economic exchanges.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Market'
    _property_uris: ClassVar[dict] = {'hasMarketSegment': 'http://ontology.naas.ai/abi/hasMarketSegment', 'isMarketOf': 'http://ontology.naas.ai/abi/isMarketOf', 'isTargetedBy': 'http://ontology.naas.ai/abi/isTargetedBy'}

    # Object properties
    hasMarketSegment: Optional[MarketSegment] = Field(default=None)
    isMarketOf: Optional[Any] = Field(default=None)
    isTargetedBy: Optional[Offering] = Field(default=None)

class Product(Offering, RDFEntity):
    """
    Product
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Product'
    _property_uris: ClassVar[dict] = {'isOfferingOf': 'http://ontology.naas.ai/abi/isOfferingOf', 'market_share': 'http://ontology.naas.ai/abi/market_share', 'targets': 'http://ontology.naas.ai/abi/Targets'}

    # Data properties
    market_share: Optional[Any] = Field(default=None)

    # Object properties
    isOfferingOf: Optional[Any] = Field(default=None)
    targets: Optional[Market] = Field(default=None)

class Service(Offering, RDFEntity):
    """
    Service
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Service'
    _property_uris: ClassVar[dict] = {'isOfferingOf': 'http://ontology.naas.ai/abi/isOfferingOf', 'market_share': 'http://ontology.naas.ai/abi/market_share', 'targets': 'http://ontology.naas.ai/abi/Targets'}

    # Data properties
    market_share: Optional[Any] = Field(default=None)

    # Object properties
    isOfferingOf: Optional[Any] = Field(default=None)
    targets: Optional[Market] = Field(default=None)

class Solution(Offering, RDFEntity):
    """
    Solution
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Solution'
    _property_uris: ClassVar[dict] = {'isOfferingOf': 'http://ontology.naas.ai/abi/isOfferingOf', 'market_share': 'http://ontology.naas.ai/abi/market_share', 'targets': 'http://ontology.naas.ai/abi/Targets'}

    # Data properties
    market_share: Optional[Any] = Field(default=None)

    # Object properties
    isOfferingOf: Optional[Any] = Field(default=None)
    targets: Optional[Market] = Field(default=None)

class MarketSegment(Market, RDFEntity):
    """
    A market segment is a more focused abstraction that describes a particular portion of a market with shared attributes. It is best categorized as a Descriptive Information Content Entity that details the specific traits and preferences of a particular group within the larger market.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/MarketSegment'
    _property_uris: ClassVar[dict] = {'hasMarketSegment': 'http://ontology.naas.ai/abi/hasMarketSegment', 'isMarketOf': 'http://ontology.naas.ai/abi/isMarketOf', 'isMarketSegmentOf': 'http://ontology.naas.ai/abi/isMarketSegmentOf', 'isTargetedBy': 'http://ontology.naas.ai/abi/isTargetedBy'}

    # Object properties
    hasMarketSegment: Optional[MarketSegment] = Field(default=None)
    isMarketOf: Optional[Any] = Field(default=None)
    isMarketSegmentOf: Optional[Market] = Field(default=None)
    isTargetedBy: Optional[Offering] = Field(default=None)

# Rebuild models to resolve forward references
Offering.model_rebuild()
Market.model_rebuild()
Product.model_rebuild()
Service.model_rebuild()
Solution.model_rebuild()
MarketSegment.model_rebuild()
