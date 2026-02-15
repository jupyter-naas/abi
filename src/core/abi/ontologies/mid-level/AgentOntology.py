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


class Ont00000026(RDFEntity):
    """
    Hair Color
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000026'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000044(RDFEntity):
    """
    Eye Color
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000044'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000084(RDFEntity):
    """
    Bodily Component
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000084'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b2(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b2'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000102(RDFEntity):
    """
    Skin Type is classified according to a reference system such as the Fitzpatrick scale: https://en.wikipedia.org/wiki/Fitzpatrick_scale
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000102'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000173(RDFEntity):
    """
    Civilian Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000173'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000175(RDFEntity):
    """
    Organization Member Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000175'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b8(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b8'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000177(RDFEntity):
    """
    Affordance
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000177'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000187(RDFEntity):
    """
    Authority Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000187'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000207(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000207'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b12(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b12'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000318(RDFEntity):
    """
    Disease
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000318'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000377(RDFEntity):
    """
    Disability
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000377'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b17(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b17'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000392(RDFEntity):
    """
    Allegiance Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000392'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b24(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b24'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000472(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000472'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000485(RDFEntity):
    """
    Commercial Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000485'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000487(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000487'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000506(RDFEntity):
    """
    Contractor Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000506'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b30(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b30'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000551(RDFEntity):
    """
    Organism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000551'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b34(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b34'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b38(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b38'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000599(RDFEntity):
    """
    Interpersonal Relationship Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000599'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000608(RDFEntity):
    """
    Financial Value
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000608'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b42(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b42'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b46(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b46'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b50(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b50'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b55(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b55'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b59(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b59'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b63(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b63'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b67(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b67'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000780(RDFEntity):
    """
    Ethnicity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000780'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b71(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b71'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000898(RDFEntity):
    """
    Geopolitical Power Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000898'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000917(RDFEntity):
    """
    Permanent Resident Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000917'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000958(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000958'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000965(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000965'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000984(RDFEntity):
    """
    Occupation Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000984'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000987(RDFEntity):
    """
    Citizen Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000987'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001006(RDFEntity):
    """
    Operator Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001006'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001017(RDFEntity):
    """
    Agent
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001017'
    _property_uris: ClassVar[dict] = {'ont00001787': 'https://www.commoncoreontologies.org/ont00001787', 'ont00001813': 'https://www.commoncoreontologies.org/ont00001813', 'ont00001852': 'https://www.commoncoreontologies.org/ont00001852', 'ont00001895': 'https://www.commoncoreontologies.org/ont00001895', 'ont00001939': 'https://www.commoncoreontologies.org/ont00001939', 'ont00001954': 'https://www.commoncoreontologies.org/ont00001954', 'ont00001977': 'https://www.commoncoreontologies.org/ont00001977', 'ont00001978': 'https://www.commoncoreontologies.org/ont00001978', 'ont00001984': 'https://www.commoncoreontologies.org/ont00001984', 'ont00001993': 'https://www.commoncoreontologies.org/ont00001993'}

    # Object properties
    ont00001787: Optional[Any] = Field(default=None)
    ont00001813: Optional[Any] = Field(default=None)
    ont00001852: Optional[Any] = Field(default=None)
    ont00001895: Optional[Any] = Field(default=None)
    ont00001939: Optional[Ont00001017] = Field(default=None)
    ont00001954: Optional[Ont00001379] = Field(default=None)
    ont00001977: Optional[Ont00001017] = Field(default=None)
    ont00001978: Optional[Any] = Field(default=None)
    ont00001984: Optional[Any] = Field(default=None)
    ont00001993: Optional[Any] = Field(default=None)

class N29c4c19552f24525b2768166f8255f97b79(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b79'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001033(RDFEntity):
    """
    Biological Sex
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001033'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b85(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b85'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b89(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b89'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b93(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b93'
    _property_uris: ClassVar[dict] = {}
    pass

class N29c4c19552f24525b2768166f8255f97b99(RDFEntity):
    _class_uri: ClassVar[str] = 'n29c4c19552f24525b2768166f8255f97b99'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001341(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001341'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001379(RDFEntity):
    """
    Agent Capability
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001379'
    _property_uris: ClassVar[dict] = {'ont00001880': 'https://www.commoncoreontologies.org/ont00001880', 'ont00001889': 'https://www.commoncoreontologies.org/ont00001889'}

    # Object properties
    ont00001880: Optional[Any] = Field(default=None)
    ont00001889: Optional[Ont00001017] = Field(default=None)

class Ont00000058(Ont00000084, RDFEntity):
    """
    Scalp Hair
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000058'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000089(Ont00001379, RDFEntity):
    """
    Skill
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000089'
    _property_uris: ClassVar[dict] = {'ont00001880': 'https://www.commoncoreontologies.org/ont00001880', 'ont00001889': 'https://www.commoncoreontologies.org/ont00001889'}

    # Object properties
    ont00001880: Optional[Any] = Field(default=None)
    ont00001889: Optional[Ont00001017] = Field(default=None)

class Ont00000129(Ont00000084, RDFEntity):
    """
    Tattoo
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000129'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000157(Ont00000084, RDFEntity):
    """
    Facial Hair
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000157'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000279(Ont00000392, RDFEntity):
    """
    Enemy Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000279'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000300(N29c4c19552f24525b2768166f8255f97b12, RDFEntity):
    """
    Group of Agents
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000300'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000404(Ont00000084, RDFEntity):
    """
    Iris
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000404'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000476(Ont00000965, RDFEntity):
    """
    Objective
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000476'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000486(Ont00000392, RDFEntity):
    """
    Neutral Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000486'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000500(Ont00000084, RDFEntity):
    """
    Eye
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000500'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000562(Ont00000551, RDFEntity):
    """
    Animal
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000562'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000567(Ont00000487, RDFEntity):
    """
    This is a general term that applies to both military and civilian activities, such as the Geospatial Region within which a company conducts its business.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000567'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000568(Ont00001379, RDFEntity):
    """
    Organization Capability
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000568'
    _property_uris: ClassVar[dict] = {'ont00001880': 'https://www.commoncoreontologies.org/ont00001880', 'ont00001889': 'https://www.commoncoreontologies.org/ont00001889'}

    # Object properties
    ont00001880: Optional[Any] = Field(default=None)
    ont00001889: Optional[Ont00001017] = Field(default=None)

class Ont00000576(Ont00000084, RDFEntity):
    """
    Scalp
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000576'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000587(Ont00000392, RDFEntity):
    """
    Ally Role
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000587'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000616(Ont00000958, RDFEntity):
    """
    Religion
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000616'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000662(Ont00001341, RDFEntity):
    """
    Material Territory of a Government Domain
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000662'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000685(Ont00000207, RDFEntity):
    """
    Government Domain Border
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000685'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000696(Ont00000958, RDFEntity):
    """
    Ideology
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000696'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000871(Ont00000551, RDFEntity):
    """
    Plant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000871'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000974(Ont00000965, RDFEntity):
    """
    Plan
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000974'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000986(Ont00000084, RDFEntity):
    """
    Scar
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000986'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001073(Ont00000608, RDFEntity):
    """
    Financial Value of Property
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001073'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001114(Ont00000472, RDFEntity):
    """
    Instances of this class are not proper Delimiting Domains, but in some cases may have an organization that exercises some control over the region, such as the homeowners' association for a neighborhood.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001114'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001125(Ont00000084, RDFEntity):
    """
    Set of Eyes
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001125'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001203(Ont00000472, RDFEntity):
    """
    Delimiting Domain
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001203'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00001212(Ont00001033, RDFEntity):
    """
    Female Sex
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001212'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001324(Ont00000965, RDFEntity):
    """
    Process Regulation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001324'
    _property_uris: ClassVar[dict] = {'ont00001800': 'https://www.commoncoreontologies.org/ont00001800', 'ont00001910': 'https://www.commoncoreontologies.org/ont00001910', 'ont00001974': 'https://www.commoncoreontologies.org/ont00001974'}

    # Object properties
    ont00001800: Optional[Any] = Field(default=None)
    ont00001910: Optional[Any] = Field(default=None)
    ont00001974: Optional[Any] = Field(default=None)

class Ont00001363(Ont00001033, RDFEntity):
    """
    Male Sex
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001363'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000181(Ont00000089, RDFEntity):
    """
    Language Skill
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000181'
    _property_uris: ClassVar[dict] = {'ont00001880': 'https://www.commoncoreontologies.org/ont00001880', 'ont00001889': 'https://www.commoncoreontologies.org/ont00001889'}

    # Object properties
    ont00001880: Optional[Any] = Field(default=None)
    ont00001889: Optional[Ont00001017] = Field(default=None)

class Ont00000553(Ont00001324, RDFEntity):
    """
    Process Prohibition
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000553'
    _property_uris: ClassVar[dict] = {'ont00001800': 'https://www.commoncoreontologies.org/ont00001800', 'ont00001910': 'https://www.commoncoreontologies.org/ont00001910', 'ont00001974': 'https://www.commoncoreontologies.org/ont00001974'}

    # Object properties
    ont00001800: Optional[Any] = Field(default=None)
    ont00001910: Optional[Any] = Field(default=None)
    ont00001974: Optional[Any] = Field(default=None)

class Ont00000631(Ont00000662, RDFEntity):
    """
    Material Territory of a Country
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000631'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000751(Ont00001324, RDFEntity):
    """
    Action Permission
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000751'
    _property_uris: ClassVar[dict] = {'ont00001800': 'https://www.commoncoreontologies.org/ont00001800', 'ont00001910': 'https://www.commoncoreontologies.org/ont00001910', 'ont00001974': 'https://www.commoncoreontologies.org/ont00001974'}

    # Object properties
    ont00001800: Optional[Any] = Field(default=None)
    ont00001910: Optional[Any] = Field(default=None)
    ont00001974: Optional[Any] = Field(default=None)

class Ont00000914(Ont00000300, RDFEntity):
    """
    Group of Persons
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000914'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000976(Ont00000696, RDFEntity):
    """
    Political Orientation
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000976'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001062(Ont00000300, RDFEntity):
    """
    International Community
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001062'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001152(Ont00001203, RDFEntity):
    """
    Government Domain
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001152'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00001180(Ont00000300, RDFEntity):
    """
    Members of organizations are either Organizations themselves or individual Persons. Members can bear specific Organization Member Roles that are determined in the organization rules. The organization rules also determine how decisions are made on behalf of the Organization by the organization members.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001180'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00001183(Ont00000300, RDFEntity):
    """
    Social Network
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001183'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001224(Ont00001324, RDFEntity):
    """
    Process Requirement
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001224'
    _property_uris: ClassVar[dict] = {'ont00001800': 'https://www.commoncoreontologies.org/ont00001800', 'ont00001910': 'https://www.commoncoreontologies.org/ont00001910', 'ont00001974': 'https://www.commoncoreontologies.org/ont00001974'}

    # Object properties
    ont00001800: Optional[Any] = Field(default=None)
    ont00001910: Optional[Any] = Field(default=None)
    ont00001974: Optional[Any] = Field(default=None)

class Ont00001239(Ont00000300, RDFEntity):
    """
    Group of Organizations
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001239'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001262(Ont00000562, RDFEntity):
    """
    Person
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001262'
    _property_uris: ClassVar[dict] = {'ont00001798': 'https://www.commoncoreontologies.org/ont00001798', 'ont00001865': 'https://www.commoncoreontologies.org/ont00001865', 'ont00001943': 'https://www.commoncoreontologies.org/ont00001943', 'ont00001995': 'https://www.commoncoreontologies.org/ont00001995'}

    # Object properties
    ont00001798: Optional[Ont00001262] = Field(default=None)
    ont00001865: Optional[Ont00001262] = Field(default=None)
    ont00001943: Optional[Ont00001262] = Field(default=None)
    ont00001995: Optional[Ont00001262] = Field(default=None)

class Ont00000010(Ont00001180, RDFEntity):
    """
    Incorporated Organization
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000010'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000126(Ont00001152, RDFEntity):
    """
    First-Order Administrative Region
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000126'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000134(Ont00001152, RDFEntity):
    """
    Third-Order Administrative Region
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000134'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000139(Ont00001152, RDFEntity):
    """
    Domain of a Country
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000139'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000141(Ont00000914, RDFEntity):
    """
    Populace
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000141'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000176(Ont00001180, RDFEntity):
    """
    Geopolitical Organization
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000176'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000274(Ont00001180, RDFEntity):
    """
    Armed Force
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000274'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000388(Ont00001262, RDFEntity):
    """
    Citizen
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000388'
    _property_uris: ClassVar[dict] = {'ont00001798': 'https://www.commoncoreontologies.org/ont00001798', 'ont00001865': 'https://www.commoncoreontologies.org/ont00001865', 'ont00001943': 'https://www.commoncoreontologies.org/ont00001943', 'ont00001995': 'https://www.commoncoreontologies.org/ont00001995'}

    # Object properties
    ont00001798: Optional[Ont00001262] = Field(default=None)
    ont00001865: Optional[Ont00001262] = Field(default=None)
    ont00001943: Optional[Ont00001262] = Field(default=None)
    ont00001995: Optional[Ont00001262] = Field(default=None)

class Ont00000405(Ont00001152, RDFEntity):
    """
    Second-Order Administrative Region
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000405'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000408(Ont00001180, RDFEntity):
    """
    Government Organization
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000408'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000443(Ont00001180, RDFEntity):
    """
    Commercial Organization
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000443'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000460(Ont00001152, RDFEntity):
    """
    Local Administrative Region
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000460'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000473(Ont00001152, RDFEntity):
    """
    Fourth-Order Administrative Region
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000473'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000507(Ont00000914, RDFEntity):
    """
    Ethnic Group
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000507'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000509(Ont00001180, RDFEntity):
    """
    Service Provider
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000509'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000564(Ont00001180, RDFEntity):
    """
    Educational Organization
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000564'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000645(Ont00001262, RDFEntity):
    """
    Permanent Resident
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000645'
    _property_uris: ClassVar[dict] = {'ont00001798': 'https://www.commoncoreontologies.org/ont00001798', 'ont00001865': 'https://www.commoncoreontologies.org/ont00001865', 'ont00001943': 'https://www.commoncoreontologies.org/ont00001943', 'ont00001995': 'https://www.commoncoreontologies.org/ont00001995'}

    # Object properties
    ont00001798: Optional[Ont00001262] = Field(default=None)
    ont00001865: Optional[Ont00001262] = Field(default=None)
    ont00001943: Optional[Ont00001262] = Field(default=None)
    ont00001995: Optional[Ont00001262] = Field(default=None)

class Ont00000647(Ont00001262, RDFEntity):
    """
    Organization Member
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000647'
    _property_uris: ClassVar[dict] = {'ont00001798': 'https://www.commoncoreontologies.org/ont00001798', 'ont00001865': 'https://www.commoncoreontologies.org/ont00001865', 'ont00001943': 'https://www.commoncoreontologies.org/ont00001943', 'ont00001995': 'https://www.commoncoreontologies.org/ont00001995'}

    # Object properties
    ont00001798: Optional[Ont00001262] = Field(default=None)
    ont00001865: Optional[Ont00001262] = Field(default=None)
    ont00001943: Optional[Ont00001262] = Field(default=None)
    ont00001995: Optional[Ont00001262] = Field(default=None)

class Ont00000666(Ont00001262, RDFEntity):
    """
    Neutral Person
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000666'
    _property_uris: ClassVar[dict] = {'ont00001798': 'https://www.commoncoreontologies.org/ont00001798', 'ont00001865': 'https://www.commoncoreontologies.org/ont00001865', 'ont00001943': 'https://www.commoncoreontologies.org/ont00001943', 'ont00001995': 'https://www.commoncoreontologies.org/ont00001995'}

    # Object properties
    ont00001798: Optional[Ont00001262] = Field(default=None)
    ont00001865: Optional[Ont00001262] = Field(default=None)
    ont00001943: Optional[Ont00001262] = Field(default=None)
    ont00001995: Optional[Ont00001262] = Field(default=None)

class Ont00000697(Ont00001262, RDFEntity):
    """
    Enemy Person
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000697'
    _property_uris: ClassVar[dict] = {'ont00001798': 'https://www.commoncoreontologies.org/ont00001798', 'ont00001865': 'https://www.commoncoreontologies.org/ont00001865', 'ont00001943': 'https://www.commoncoreontologies.org/ont00001943', 'ont00001995': 'https://www.commoncoreontologies.org/ont00001995'}

    # Object properties
    ont00001798: Optional[Ont00001262] = Field(default=None)
    ont00001865: Optional[Ont00001262] = Field(default=None)
    ont00001943: Optional[Ont00001262] = Field(default=None)
    ont00001995: Optional[Ont00001262] = Field(default=None)

class Ont00000837(Ont00000914, RDFEntity):
    """
    Family
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000837'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000860(Ont00001262, RDFEntity):
    """
    Allied Person
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000860'
    _property_uris: ClassVar[dict] = {'ont00001798': 'https://www.commoncoreontologies.org/ont00001798', 'ont00001865': 'https://www.commoncoreontologies.org/ont00001865', 'ont00001943': 'https://www.commoncoreontologies.org/ont00001943', 'ont00001995': 'https://www.commoncoreontologies.org/ont00001995'}

    # Object properties
    ont00001798: Optional[Ont00001262] = Field(default=None)
    ont00001865: Optional[Ont00001262] = Field(default=None)
    ont00001943: Optional[Ont00001262] = Field(default=None)
    ont00001995: Optional[Ont00001262] = Field(default=None)

class Ont00001164(Ont00001152, RDFEntity):
    """
    County
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001164'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00001284(Ont00000914, RDFEntity):
    """
    Crew
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001284'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001302(Ont00001180, RDFEntity):
    """
    Civil Organization
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001302'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00001335(Ont00001180, RDFEntity):
    """
    Government
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001335'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000046(Ont00000126, RDFEntity):
    """
    Province
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000046'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000071(Ont00000460, RDFEntity):
    """
    Town
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000071'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000383(Ont00000837, RDFEntity):
    """
    Nuclear Family
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000383'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000426(Ont00000274, RDFEntity):
    """
    Military Personnel Force
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000426'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000532(Ont00001335, RDFEntity):
    """
    Government of a Country
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000532'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00000718(Ont00000460, RDFEntity):
    """
    Village
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000718'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000887(Ont00000460, RDFEntity):
    """
    City
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000887'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00000934(Ont00000126, RDFEntity):
    """
    Constituent State
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000934'
    _property_uris: ClassVar[dict] = {'ont00001864': 'https://www.commoncoreontologies.org/ont00001864'}

    # Object properties
    ont00001864: Optional[Ont00001180] = Field(default=None)

class Ont00001312(Ont00000274, RDFEntity):
    """
    Paramilitary Force
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001312'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

class Ont00001276(Ont00000426, RDFEntity):
    """
    Carrier Air Wing
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001276'
    _property_uris: ClassVar[dict] = {'ont00001794': 'https://www.commoncoreontologies.org/ont00001794', 'ont00001815': 'https://www.commoncoreontologies.org/ont00001815', 'ont00001846': 'https://www.commoncoreontologies.org/ont00001846', 'ont00001859': 'https://www.commoncoreontologies.org/ont00001859'}

    # Object properties
    ont00001794: Optional[Ont00001180] = Field(default=None)
    ont00001815: Optional[Ont00001180] = Field(default=None)
    ont00001846: Optional[Any] = Field(default=None)
    ont00001859: Optional[Ont00001203] = Field(default=None)

# Rebuild models to resolve forward references
Ont00000026.model_rebuild()
Ont00000044.model_rebuild()
Ont00000084.model_rebuild()
N29c4c19552f24525b2768166f8255f97b2.model_rebuild()
Ont00000102.model_rebuild()
Ont00000173.model_rebuild()
Ont00000175.model_rebuild()
N29c4c19552f24525b2768166f8255f97b8.model_rebuild()
Ont00000177.model_rebuild()
Ont00000187.model_rebuild()
Ont00000207.model_rebuild()
N29c4c19552f24525b2768166f8255f97b12.model_rebuild()
Ont00000318.model_rebuild()
Ont00000377.model_rebuild()
N29c4c19552f24525b2768166f8255f97b17.model_rebuild()
Ont00000392.model_rebuild()
N29c4c19552f24525b2768166f8255f97b24.model_rebuild()
Ont00000472.model_rebuild()
Ont00000485.model_rebuild()
Ont00000487.model_rebuild()
Ont00000506.model_rebuild()
N29c4c19552f24525b2768166f8255f97b30.model_rebuild()
Ont00000551.model_rebuild()
N29c4c19552f24525b2768166f8255f97b34.model_rebuild()
N29c4c19552f24525b2768166f8255f97b38.model_rebuild()
Ont00000599.model_rebuild()
Ont00000608.model_rebuild()
N29c4c19552f24525b2768166f8255f97b42.model_rebuild()
N29c4c19552f24525b2768166f8255f97b46.model_rebuild()
N29c4c19552f24525b2768166f8255f97b50.model_rebuild()
N29c4c19552f24525b2768166f8255f97b55.model_rebuild()
N29c4c19552f24525b2768166f8255f97b59.model_rebuild()
N29c4c19552f24525b2768166f8255f97b63.model_rebuild()
N29c4c19552f24525b2768166f8255f97b67.model_rebuild()
Ont00000780.model_rebuild()
N29c4c19552f24525b2768166f8255f97b71.model_rebuild()
Ont00000898.model_rebuild()
Ont00000917.model_rebuild()
Ont00000958.model_rebuild()
Ont00000965.model_rebuild()
Ont00000984.model_rebuild()
Ont00000987.model_rebuild()
Ont00001006.model_rebuild()
Ont00001017.model_rebuild()
N29c4c19552f24525b2768166f8255f97b79.model_rebuild()
Ont00001033.model_rebuild()
N29c4c19552f24525b2768166f8255f97b85.model_rebuild()
N29c4c19552f24525b2768166f8255f97b89.model_rebuild()
N29c4c19552f24525b2768166f8255f97b93.model_rebuild()
N29c4c19552f24525b2768166f8255f97b99.model_rebuild()
Ont00001341.model_rebuild()
Ont00001379.model_rebuild()
Ont00000058.model_rebuild()
Ont00000089.model_rebuild()
Ont00000129.model_rebuild()
Ont00000157.model_rebuild()
Ont00000279.model_rebuild()
Ont00000300.model_rebuild()
Ont00000404.model_rebuild()
Ont00000476.model_rebuild()
Ont00000486.model_rebuild()
Ont00000500.model_rebuild()
Ont00000562.model_rebuild()
Ont00000567.model_rebuild()
Ont00000568.model_rebuild()
Ont00000576.model_rebuild()
Ont00000587.model_rebuild()
Ont00000616.model_rebuild()
Ont00000662.model_rebuild()
Ont00000685.model_rebuild()
Ont00000696.model_rebuild()
Ont00000871.model_rebuild()
Ont00000974.model_rebuild()
Ont00000986.model_rebuild()
Ont00001073.model_rebuild()
Ont00001114.model_rebuild()
Ont00001125.model_rebuild()
Ont00001203.model_rebuild()
Ont00001212.model_rebuild()
Ont00001324.model_rebuild()
Ont00001363.model_rebuild()
Ont00000181.model_rebuild()
Ont00000553.model_rebuild()
Ont00000631.model_rebuild()
Ont00000751.model_rebuild()
Ont00000914.model_rebuild()
Ont00000976.model_rebuild()
Ont00001062.model_rebuild()
Ont00001152.model_rebuild()
Ont00001180.model_rebuild()
Ont00001183.model_rebuild()
Ont00001224.model_rebuild()
Ont00001239.model_rebuild()
Ont00001262.model_rebuild()
Ont00000010.model_rebuild()
Ont00000126.model_rebuild()
Ont00000134.model_rebuild()
Ont00000139.model_rebuild()
Ont00000141.model_rebuild()
Ont00000176.model_rebuild()
Ont00000274.model_rebuild()
Ont00000388.model_rebuild()
Ont00000405.model_rebuild()
Ont00000408.model_rebuild()
Ont00000443.model_rebuild()
Ont00000460.model_rebuild()
Ont00000473.model_rebuild()
Ont00000507.model_rebuild()
Ont00000509.model_rebuild()
Ont00000564.model_rebuild()
Ont00000645.model_rebuild()
Ont00000647.model_rebuild()
Ont00000666.model_rebuild()
Ont00000697.model_rebuild()
Ont00000837.model_rebuild()
Ont00000860.model_rebuild()
Ont00001164.model_rebuild()
Ont00001284.model_rebuild()
Ont00001302.model_rebuild()
Ont00001335.model_rebuild()
Ont00000046.model_rebuild()
Ont00000071.model_rebuild()
Ont00000383.model_rebuild()
Ont00000426.model_rebuild()
Ont00000532.model_rebuild()
Ont00000718.model_rebuild()
Ont00000887.model_rebuild()
Ont00000934.model_rebuild()
Ont00001312.model_rebuild()
Ont00001276.model_rebuild()
