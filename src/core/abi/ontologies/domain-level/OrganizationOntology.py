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


class Website(RDFEntity):
    """
    Website
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Website'
    _property_uris: ClassVar[dict] = {'isWebsiteOf': 'http://ontology.naas.ai/abi/isWebsiteOf'}

    # Object properties
    isWebsiteOf: Optional[Any] = Field(default=None)

class Ticker(RDFEntity):
    """
    Ticker
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Ticker'
    _property_uris: ClassVar[dict] = {'isTickerSymbolOf': 'http://ontology.naas.ai/abi/isTickerSymbolOf'}

    # Object properties
    isTickerSymbolOf: Optional[Any] = Field(default=None)

class Industry(RDFEntity):
    """
    Industry
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Industry'
    _property_uris: ClassVar[dict] = {}
    pass

class TechnologicalCapabilities(RDFEntity):
    """
    Technological Capabilities are the technological abilities, systems, and expertise possessed by an organization.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/TechnologicalCapabilities'
    _property_uris: ClassVar[dict] = {}
    pass

class HumanCapabilities(RDFEntity):
    """
    Human Capabilities are the skills, knowledge, and expertise possessed by an organization's workforce.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/HumanCapabilities'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfPartnership(RDFEntity):
    """
    Act of Partnership
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfPartnership'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfJointVenture(RDFEntity):
    """
    Act of Joint Venture
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfJointVenture'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfMarketingAlliance(RDFEntity):
    """
    Act of Marketing Alliance
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfMarketingAlliance'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfResearchCollaboration(RDFEntity):
    """
    Research Collaborations represent formal partnerships focused on research and development activities.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfResearchCollaboration'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfTechnologyLicensing(RDFEntity):
    """
    Act of Technology Licensing
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfTechnologyLicensing'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfDistributionAgreement(RDFEntity):
    """
    Act of Distribution Agreement
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfDistributionAgreement'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfOrganizationalMerger(RDFEntity):
    """
    Act of Organizational Merger
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfOrganizationalMerger'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfOrganizationalAcquisition(RDFEntity):
    """
    Act of Organizational Acquisition
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfOrganizationalAcquisition'
    _property_uris: ClassVar[dict] = {}
    pass

class ActOfSubsidiaryEstablishment(RDFEntity):
    """
    Act of Subsidiary Establishment
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ActOfSubsidiaryEstablishment'
    _property_uris: ClassVar[dict] = {}
    pass

class GlobalHeadquarters(RDFEntity):
    """
    A Facility that serves as the central office for an organization on a global scale, providing strategic direction and administrative functions across all regions where the organization operates.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/GlobalHeadquarters'
    _property_uris: ClassVar[dict] = {}
    pass

class RegionalHeadquarters(RDFEntity):
    """
    A Facility that serves as the central office for an organization within a specific region, overseeing operations and providing strategic direction and administrative functions for that region.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/RegionalHeadquarters'
    _property_uris: ClassVar[dict] = {}
    pass

class Brand(RDFEntity):
    """
    Brands are informational constructs that encapsulate the reputation and identity of products or services, making them suitable to be represented as Descriptive Information Content Entities.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Brand'
    _property_uris: ClassVar[dict] = {}
    pass

class StrategicAlliance(RDFEntity):
    """
    Strategic alliances are typically formalized through documents and agreements, making them apt to be represented as Descriptive Information Content Entities.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/StrategicAlliance'
    _property_uris: ClassVar[dict] = {}
    pass

class OrganizationMerger(RDFEntity):
    """
    A merger is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/OrganizationMerger'
    _property_uris: ClassVar[dict] = {}
    pass

class OrganizationAcquisition(RDFEntity):
    """
    An organization acquisition is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/OrganizationAcquisition'
    _property_uris: ClassVar[dict] = {}
    pass

class Partnership(StrategicAlliance, RDFEntity):
    """
    A partnership is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/Partnership'
    _property_uris: ClassVar[dict] = {}
    pass

class JointVenture(StrategicAlliance, RDFEntity):
    """
    A joint venture is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/JointVenture'
    _property_uris: ClassVar[dict] = {}
    pass

class MarketingAlliance(StrategicAlliance, RDFEntity):
    """
    A marketing alliance is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/MarketingAlliance'
    _property_uris: ClassVar[dict] = {}
    pass

class ResearchCollaboration(StrategicAlliance, RDFEntity):
    """
    A research collaboration is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/ResearchCollaboration'
    _property_uris: ClassVar[dict] = {}
    pass

class TechnologyLicensing(StrategicAlliance, RDFEntity):
    """
    A technology licensing is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/TechnologyLicensing'
    _property_uris: ClassVar[dict] = {}
    pass

class DistributionAgreement(StrategicAlliance, RDFEntity):
    """
    A distribution agreement is often documented through agreements and plans, which makes it suitable to be represented as a Descriptive Information Content Entity.
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/DistributionAgreement'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Website.model_rebuild()
Ticker.model_rebuild()
Industry.model_rebuild()
TechnologicalCapabilities.model_rebuild()
HumanCapabilities.model_rebuild()
ActOfPartnership.model_rebuild()
ActOfJointVenture.model_rebuild()
ActOfMarketingAlliance.model_rebuild()
ActOfResearchCollaboration.model_rebuild()
ActOfTechnologyLicensing.model_rebuild()
ActOfDistributionAgreement.model_rebuild()
ActOfOrganizationalMerger.model_rebuild()
ActOfOrganizationalAcquisition.model_rebuild()
ActOfSubsidiaryEstablishment.model_rebuild()
GlobalHeadquarters.model_rebuild()
RegionalHeadquarters.model_rebuild()
Brand.model_rebuild()
StrategicAlliance.model_rebuild()
OrganizationMerger.model_rebuild()
OrganizationAcquisition.model_rebuild()
Partnership.model_rebuild()
JointVenture.model_rebuild()
MarketingAlliance.model_rebuild()
ResearchCollaboration.model_rebuild()
TechnologyLicensing.model_rebuild()
DistributionAgreement.model_rebuild()
