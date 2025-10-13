from __future__ import annotations
from typing import Optional, Any, ClassVar
from pydantic import BaseModel, Field
import datetime
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


class N2bfb5da6e2194aa7ba47ffc474ebfe37b5(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b5'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000223(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000223'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000253(RDFEntity):
    """
    This class continues to use the word ‘bearing’ in its rdfslabel because of potential confusion with the acronym ‘ICE’, which is widely used for information content entity.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000253'
    _property_uris: ClassVar[dict] = {'ont00001765': 'https://www.commoncoreontologies.org/ont00001765', 'ont00001767': 'https://www.commoncoreontologies.org/ont00001767', 'ont00001768': 'https://www.commoncoreontologies.org/ont00001768', 'ont00001769': 'https://www.commoncoreontologies.org/ont00001769', 'ont00001770': 'https://www.commoncoreontologies.org/ont00001770', 'ont00001771': 'https://www.commoncoreontologies.org/ont00001771', 'ont00001772': 'https://www.commoncoreontologies.org/ont00001772', 'ont00001773': 'https://www.commoncoreontologies.org/ont00001773', 'ont00001824': 'https://www.commoncoreontologies.org/ont00001824', 'ont00001863': 'https://www.commoncoreontologies.org/ont00001863', 'ont00001878': 'https://www.commoncoreontologies.org/ont00001878', 'ont00001908': 'https://www.commoncoreontologies.org/ont00001908', 'ont00001912': 'https://www.commoncoreontologies.org/ont00001912', 'ont00001913': 'https://www.commoncoreontologies.org/ont00001913', 'ont00001976': 'https://www.commoncoreontologies.org/ont00001976'}

    # Data properties
    ont00001765: Optional[Any] = Field(default=None)
    ont00001767: Optional[datetime.datetime] = Field(default=None)
    ont00001768: Optional[Any] = Field(default=None)
    ont00001769: Optional[Any] = Field(default=None)
    ont00001770: Optional[float] = Field(default=None)
    ont00001771: Optional[Any] = Field(default=None)
    ont00001772: Optional[bool] = Field(default=None)
    ont00001773: Optional[int] = Field(default=None)

    # Object properties
    ont00001824: Optional[Ont00000253] = Field(default=None)
    ont00001863: Optional[Ont00000120] = Field(default=None)
    ont00001878: Optional[Any] = Field(default=None)
    ont00001908: Optional[Ont00000829] = Field(default=None)
    ont00001912: Optional[Ont00000398] = Field(default=None)
    ont00001913: Optional[Ont00000469] = Field(default=None)
    ont00001976: Optional[Ont00001175] = Field(default=None)

class N2bfb5da6e2194aa7ba47ffc474ebfe37b10(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b10'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b14(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b14'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000314(RDFEntity):
    """
    Typically, an IQE will be a complex pattern made up of multiple qualities joined together spatially.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000314'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b19(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b19'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b23(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b23'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000498(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000498'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b27(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b27'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b31(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b31'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b35(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b35'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b40(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b40'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b47(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b47'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000958(RDFEntity):
    """
    Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000958'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class N2bfb5da6e2194aa7ba47ffc474ebfe37b51(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b51'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b55(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b55'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b59(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b59'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b63(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b63'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b67(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b67'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b71(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b71'
    _property_uris: ClassVar[dict] = {}
    pass

class N2bfb5da6e2194aa7ba47ffc474ebfe37b75(RDFEntity):
    _class_uri: ClassVar[str] = 'n2bfb5da6e2194aa7ba47ffc474ebfe37b75'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000686(Ont00000958, RDFEntity):
    """
    Designative Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000686'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000853(Ont00000958, RDFEntity):
    """
    Descriptive Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000853'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000965(Ont00000958, RDFEntity):
    """
    Prescriptive Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000965'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001942': 'https://www.commoncoreontologies.org/ont00001942'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001942: Optional[Any] = Field(default=None)

class Ont00001069(Ont00000958, RDFEntity):
    """
    Representational Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001069'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002001(Ont00000958, RDFEntity):
    """
    By 'canonical', it is intended that the media format is of a commonly recognized format, such as mass media formats such as books, magazines, and journals, as well as digital media forms (e.g. ebooks), to include, too, file types, such as those recognized by the Internet Assigned Numbers Authority (IANA)'s Media Types standard [RFC2046].
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002001'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000003(Ont00000686, RDFEntity):
    """
    Designative Name
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000003'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000120(Ont00000853, RDFEntity):
    """
    Measurement Unit
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000120'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001961': 'https://www.commoncoreontologies.org/ont00001961', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001961: Optional[Ont00000253] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000127(Ont00000965, RDFEntity):
    """
    Performance Specification
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000127'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001942': 'https://www.commoncoreontologies.org/ont00001942', 'ont00001980': 'https://www.commoncoreontologies.org/ont00001980'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001942: Optional[Any] = Field(default=None)
    ont00001980: Optional[Any] = Field(default=None)

class Ont00000390(Ont00000686, RDFEntity):
    """
    Spatial Region Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000390'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000398(Ont00000853, RDFEntity):
    """
    Reference System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000398'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000399(Ont00000686, RDFEntity):
    """
    Temporal Region Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000399'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000626(Ont00000853, RDFEntity):
    """
    Since predictions are inherently about not-yet-existant things, the Modal Relation Ontology term 'describes' (i.e. mro:describes) should be used (instead of the standard cco:describes) to relate instances of Predictive Information Content Entity to the entities they are about.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000626'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000649(Ont00000686, RDFEntity):
    """
    Non-Name Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000649'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000653(Ont00000965, RDFEntity):
    """
    Algorithm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000653'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001942': 'https://www.commoncoreontologies.org/ont00001942'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001942: Optional[Any] = Field(default=None)

class Ont00001163(Ont00000853, RDFEntity):
    """
    Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001163'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00001175(Ont00000965, RDFEntity):
    """
    Language
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001175'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001899': 'https://www.commoncoreontologies.org/ont00001899', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001942': 'https://www.commoncoreontologies.org/ont00001942'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001899: Optional[Ont00000253] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001942: Optional[Any] = Field(default=None)

class Ont00002002(Ont00002001, RDFEntity):
    """
    Certificate
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002002'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002004(Ont00002001, RDFEntity):
    """
    Image
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002004'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002006(Ont00002001, RDFEntity):
    """
    Database
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002006'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002007(Ont00002001, RDFEntity):
    """
    List
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002007'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002009(Ont00002001, RDFEntity):
    """
    Video
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002009'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002010(Ont00002001, RDFEntity):
    """
    Message
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002010'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002014(Ont00002001, RDFEntity):
    """
    For information on types of barcodes, see: https://www.scandit.com/types-barcodes-choosing-right-barcode/
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002014'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002037(Ont00002001, RDFEntity):
    """
    Information Line
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002037'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002038(Ont00002001, RDFEntity):
    """
    Document Field Content
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002038'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002039(Ont00002001, RDFEntity):
    """
    Document Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002039'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000073(Ont00000399, RDFEntity):
    """
    Temporal Interval Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000073'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000077(Ont00000649, RDFEntity):
    """
    Code Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000077'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000146(Ont00001175, RDFEntity):
    """
    Artificial Language
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000146'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001899': 'https://www.commoncoreontologies.org/ont00001899', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001942': 'https://www.commoncoreontologies.org/ont00001942'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001899: Optional[Ont00000253] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001942: Optional[Any] = Field(default=None)

class Ont00000275(Ont00000398, RDFEntity):
    """
    Note that, while reference systems and reference frames are treated as synonyms here, some people treat them as related but separate entities. See: http://www.ggos-portal.org/lang_en/GGOS-Portal/EN/Topics/GeodeticApplications/GeodeticReferenceSystemsAndFrames/GeodeticReferenceSystemsAndFrames.html
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000275'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000293(Ont00001163, RDFEntity):
    """
    Four of the subtypes of measurements used here (Interval, Nominal, Ordinal, and Ratio) were originally defined by S.S. Stevens in the article "On the Theory of Scales of Measurement" in Science, Vol. 103 No. 2684 on June 7, 1946. For an introductory article with links to additional content including criticisms and alternate classifications of measurements see https://en.wikipedia.org/wiki/Level_of_measurement
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000293'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001868': 'https://www.commoncoreontologies.org/ont00001868', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001868: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000406(Ont00000120, RDFEntity):
    """
    Measurement Unit of Geocoordinate
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000406'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001961': 'https://www.commoncoreontologies.org/ont00001961', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001961: Optional[Ont00000253] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000496(Ont00001175, RDFEntity):
    """
    Natural Language
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000496'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001899': 'https://www.commoncoreontologies.org/ont00001899', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001942': 'https://www.commoncoreontologies.org/ont00001942'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001899: Optional[Ont00000253] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001942: Optional[Any] = Field(default=None)

class Ont00000540(Ont00000399, RDFEntity):
    """
    Temporal Instant Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000540'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000592(Ont00001163, RDFEntity):
    """
    'Deviation Measurement Information Content Entity' and 'Veracity Measurement Information Content Entity' are complementary notions. Deviation is a measure of whether reality conforms to an ICE (e.g., a plan or prediction), whereas Veracity is a measure of whether a Descriptive ICE conforms to reality.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000592'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000605(Ont00000003, RDFEntity):
    """
    Abbreviated Name
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000605'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000692(Ont00001163, RDFEntity):
    """
    Every probability measurement is made within a particular context given certain background assumptions.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000692'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000731(Ont00001163, RDFEntity):
    """
    'Deviation Measurement Information Content Entity' and 'Veracity Measurement Information Content Entity' are complementary notions. Deviation is a measure of whether reality conforms to an ICE (e.g., a plan or prediction), whereas Veracity is a measure of whether a Descriptive ICE conforms to reality.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000731'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000829(Ont00000390, RDFEntity):
    """
    Standards of date, time, and time zone data formats:
    ISO/WD 8601-2 (http://www.loc.gov/standards/datetime/iso-tc154-wg5_n0039_iso_wd_8601-2_2016-02-16.pdf)
    W3C (https://www.w3.org/TR/NOTE-datetime)
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000829'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001837': 'https://www.commoncoreontologies.org/ont00001837', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001837: Optional[Ont00000253] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000923(Ont00000649, RDFEntity):
    """
    Arbitrary Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000923'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000990(Ont00000003, RDFEntity):
    """
    Nickname
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000990'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00001010(Ont00001163, RDFEntity):
    """
    Four of the subtypes of measurements used here (Interval, Nominal, Ordinal, and Ratio) were originally defined by S.S. Stevens in the article "On the Theory of Scales of Measurement" in Science, Vol. 103 No. 2684 on June 7, 1946. For an introductory article with links to additional content including criticisms and alternate classifications of measurements see https://en.wikipedia.org/wiki/Level_of_measurement
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001010'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001811': 'https://www.commoncoreontologies.org/ont00001811', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001811: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00001014(Ont00000003, RDFEntity):
    """
    Proper Name
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001014'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00001022(Ont00001163, RDFEntity):
    """
    Four of the subtypes of measurements used here (Interval, Nominal, Ordinal, and Ratio) were originally defined by S.S. Stevens in the article "On the Theory of Scales of Measurement" in Science, Vol. 103 No. 2684 on June 7, 1946. For an introductory article with links to additional content including criticisms and alternate classifications of measurements see https://en.wikipedia.org/wiki/Level_of_measurement
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001022'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001983': 'https://www.commoncoreontologies.org/ont00001983'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001983: Optional[Any] = Field(default=None)

class Ont00001176(Ont00001163, RDFEntity):
    """
    Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001176'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00001205(Ont00000398, RDFEntity):
    """
    Priority Scale
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001205'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00001256(Ont00001163, RDFEntity):
    """
    Note, the term 'accuracy' is avoided due to its ambiguity between: correctness-of-performance ('Reliability Measurement Information Content Entity'), correctness-of-information (see: 'Veracity Measurement Information Content Entity'), and adherance-to-expectations (see: 'Deviation Measurement Information Content Entity').
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001256'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00001328(Ont00000398, RDFEntity):
    """
    Temporal Reference System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001328'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00001364(Ont00001163, RDFEntity):
    """
    Four of the subtypes of measurements used here (Interval, Nominal, Ordinal, and Ratio) were originally defined by S.S. Stevens in the article "On the Theory of Scales of Measurement" in Science, Vol. 103 No. 2684 on June 7, 1946. For an introductory article with links to additional content including criticisms and alternate classifications of measurements see https://en.wikipedia.org/wiki/Level_of_measurement
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001364'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001877': 'https://www.commoncoreontologies.org/ont00001877', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001877: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00002003(Ont00002002, RDFEntity):
    """
    Academic Degree
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002003'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002005(Ont00002004, RDFEntity):
    """
    Chart
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002005'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002008(Ont00002007, RDFEntity):
    """
    Code List
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002008'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002011(Ont00002010, RDFEntity):
    """
    Warning Message
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002011'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002012(Ont00002010, RDFEntity):
    """
    Email Message
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002012'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002013(Ont00002010, RDFEntity):
    """
    Notification Message
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002013'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002015(Ont00002014, RDFEntity):
    """
    Two-Dimensional Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002015'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002020(Ont00002014, RDFEntity):
    """
    One-Dimensional Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002020'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002040(Ont00002039, RDFEntity):
    """
    Book
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002040'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002041(Ont00002039, RDFEntity):
    """
    Transcript
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002041'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002042(Ont00002039, RDFEntity):
    """
    Spreadsheet
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002042'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002043(Ont00002039, RDFEntity):
    """
    Report
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002043'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002044(Ont00002039, RDFEntity):
    """
    Form Document
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002044'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002045(Ont00002039, RDFEntity):
    """
    Journal Article
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002045'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000067(Ont00001328, RDFEntity):
    """
    In traditional astronomical usage, civil time is mean solar time as calculated from midnight as the beginning of the Civil Day.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000067'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000124(Ont00001328, RDFEntity):
    """
    Solar Time Reference System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000124'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000164(Ont00001010, RDFEntity):
    """
    Minimum Ordinal Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000164'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001811': 'https://www.commoncoreontologies.org/ont00001811', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001811: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000186(Ont00001010, RDFEntity):
    """
    Artifact Version Ordinality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000186'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001811': 'https://www.commoncoreontologies.org/ont00001811', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001811: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000203(Ont00000293, RDFEntity):
    """
    Event Status Nominal Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000203'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001868': 'https://www.commoncoreontologies.org/ont00001868', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001868: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000263(Ont00001328, RDFEntity):
    """
    A single Clock Time System does not provide a complete means for identifying or measuring times. Depending on the particular Clock Time System, it may be compatible for use with one or more other Temporal Reference Systems.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000263'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000369(Ont00001010, RDFEntity):
    """
    Priority Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000369'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001811': 'https://www.commoncoreontologies.org/ont00001811', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001811: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000419(Ont00000077, RDFEntity):
    """
    Part Number
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000419'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000469(Ont00000275, RDFEntity):
    """
    Geospatial Coordinate Reference System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000469'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001900': 'https://www.commoncoreontologies.org/ont00001900', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001900: Optional[Ont00000253] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000529(Ont00000073, RDFEntity):
    """
    Date Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000529'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000539(Ont00001022, RDFEntity):
    """
    Count Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000539'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001983': 'https://www.commoncoreontologies.org/ont00001983'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001983: Optional[Any] = Field(default=None)

class Ont00000604(Ont00001010, RDFEntity):
    """
    Maximum Ordinal Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000604'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001811': 'https://www.commoncoreontologies.org/ont00001811', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001811: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000669(Ont00001022, RDFEntity):
    """
    Distance Measurement Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000669'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001983': 'https://www.commoncoreontologies.org/ont00001983'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001983: Optional[Any] = Field(default=None)

class Ont00000683(Ont00000605, RDFEntity):
    """
    Diminutive Name
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000683'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000729(Ont00000275, RDFEntity):
    """
    Spherical Coordinate System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000729'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000735(Ont00000406, RDFEntity):
    """
    Geospatial Region Bounding Box Identifier List
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000735'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001961': 'https://www.commoncoreontologies.org/ont00001961', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001961: Optional[Ont00000253] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000745(Ont00001176, RDFEntity):
    """
    Point Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000745'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000827(Ont00000540, RDFEntity):
    """
    Time of Day Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000827'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000845(Ont00001022, RDFEntity):
    """
    A percentage is one way to express a proportional measure where the decimal expression of the proportion is multiplied by 100, thus giving the proportional value with respect to a whole of 100. E.g., the ratio of pigs to cows on a farm is 44 to 79 (44:79 or 44/79). The proportion of pigs to total animals is 44 to 123 or 44/123. The percentage of pigs is the decimal equivalent of the proportion (0.36) multiplied by a 100 (36%). The percentage can be expressed as a proportion where the numerator value is transformed for a denominator of 100, i.e., 36 of a 100 animals are pigs (36/100).
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000845'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001983': 'https://www.commoncoreontologies.org/ont00001983'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001983: Optional[Any] = Field(default=None)

class Ont00000891(Ont00001328, RDFEntity):
    """
    Calendar System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000891'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000915(Ont00000605, RDFEntity):
    """
    Acronym
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000915'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00001041(Ont00001010, RDFEntity):
    """
    Sequence Position Ordinality
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001041'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001811': 'https://www.commoncoreontologies.org/ont00001811', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001811: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00001101(Ont00001176, RDFEntity):
    """
    Interval Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001101'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00001146(Ont00001328, RDFEntity):
    """
    Sidereal Time is the angle measured from an observer's meridian along the celestial equator to the Great Circle that passes through the March equinox and both poles. This angle is usually expressed in Hours, Minutes, and Seconds.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001146'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00001235(Ont00000829, RDFEntity):
    """
    Military Time Zone Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001235'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001837': 'https://www.commoncoreontologies.org/ont00001837', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001837: Optional[Ont00000253] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00001238(Ont00000605, RDFEntity):
    """
    Initialism
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001238'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00001309(Ont00000077, RDFEntity):
    """
    Lot Number
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001309'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00001331(Ont00001014, RDFEntity):
    """
    Legal Name
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001331'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00001351(Ont00000275, RDFEntity):
    """
    Cartesian Coordinate System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001351'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00001352(Ont00000829, RDFEntity):
    """
    Greenwich Mean Time (GMT) is the mean solar time at the Royal Observatory in Greenwich, London and has been superseded by Coordinated Universal Time (UTC).
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001352'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001837': 'https://www.commoncoreontologies.org/ont00001837', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001837: Optional[Ont00000253] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002016(Ont00002015, RDFEntity):
    """
    Aztec Code
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002016'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002017(Ont00002015, RDFEntity):
    """
    Data Matrix Code
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002017'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002018(Ont00002015, RDFEntity):
    """
    QR Code
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002018'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002019(Ont00002015, RDFEntity):
    """
    PDF417 Code
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002019'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002021(Ont00002020, RDFEntity):
    """
    Codabar Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002021'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002022(Ont00002020, RDFEntity):
    """
    Code 93 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002022'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002023(Ont00002020, RDFEntity):
    """
    ITF Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002023'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002024(Ont00002020, RDFEntity):
    """
    MSI Plessey Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002024'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002025(Ont00002020, RDFEntity):
    """
    EAN Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002025'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002031(Ont00002020, RDFEntity):
    """
    Further variants of GS1 DataBar have not been defined here.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002031'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002032(Ont00002020, RDFEntity):
    """
    Code 39 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002032'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002033(Ont00002020, RDFEntity):
    """
    Code 128 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002033'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002034(Ont00002020, RDFEntity):
    """
    UPC Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002034'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000029(Ont00000745, RDFEntity):
    """
    Median Point Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000029'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000080(Ont00000827, RDFEntity):
    """
    Standard Time of Day Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000080'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000154(Ont00000745, RDFEntity):
    """
    While there is always at least one Mode for every set of data, it is possible for any given set of data to have multiple Modes. The Mode is typically most useful when the members of the set are all Nominal Measurement Information Content Entities.
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000154'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000276(Ont00000891, RDFEntity):
    """
    Solar Calendar System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000276'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000630(Ont00000124, RDFEntity):
    """
    Universal Time Reference System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000630'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000894(Ont00000529, RDFEntity):
    """
    Decimal Date Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000894'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000896(Ont00000745, RDFEntity):
    """
    Mean Point Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000896'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00000916(Ont00000891, RDFEntity):
    """
    Lunar Calendar System
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000916'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982', 'ont00001997': 'https://www.commoncoreontologies.org/ont00001997'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)
    ont00001997: Optional[Ont00000253] = Field(default=None)

class Ont00000973(Ont00000827, RDFEntity):
    """
    Decimal Time of Day Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000973'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00001149(Ont00001101, RDFEntity):
    """
    Data Range Interval Estimate Information Content Entity
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001149'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938', 'ont00001966': 'https://www.commoncoreontologies.org/ont00001966', 'ont00001982': 'https://www.commoncoreontologies.org/ont00001982'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)
    ont00001966: Optional[Any] = Field(default=None)
    ont00001982: Optional[Any] = Field(default=None)

class Ont00001340(Ont00000529, RDFEntity):
    """
    Calendar Date Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001340'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002026(Ont00002025, RDFEntity):
    """
    ISSN Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002026'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002027(Ont00002025, RDFEntity):
    """
    JAN-13 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002027'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002028(Ont00002025, RDFEntity):
    """
    EAN-13 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002028'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002029(Ont00002025, RDFEntity):
    """
    EAN-8 Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002029'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002030(Ont00002025, RDFEntity):
    """
    ISBN Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002030'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002035(Ont00002034, RDFEntity):
    """
    UPC-A Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002035'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00002036(Ont00002034, RDFEntity):
    """
    UPC-E Barcode
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00002036'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000087(Ont00000894, RDFEntity):
    """
    An Ordinal Date Identifier may or may not also contain a number indicating a specific Year. If both numbers are included, the ISO 8601 ordinal date format stipulates that the two numbers be formatted as YYYY-DDD or YYYYDDD where [YYYY] indicates a year and [DDD] is the day of that year, from 001 through 365 (or 366 in leap years).
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000087'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000589(Ont00000973, RDFEntity):
    """
    Julian Date Fraction
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000589'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000749(Ont00000894, RDFEntity):
    """
    Julian Day Number
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000749'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

class Ont00000833(Ont00000973, RDFEntity):
    """
    Julian Date Identifier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000833'
    _property_uris: ClassVar[dict] = {'ont00001808': 'https://www.commoncoreontologies.org/ont00001808', 'ont00001916': 'https://www.commoncoreontologies.org/ont00001916', 'ont00001938': 'https://www.commoncoreontologies.org/ont00001938'}

    # Object properties
    ont00001808: Optional[Any] = Field(default=None)
    ont00001916: Optional[Any] = Field(default=None)
    ont00001938: Optional[Any] = Field(default=None)

# Rebuild models to resolve forward references
N2bfb5da6e2194aa7ba47ffc474ebfe37b5.model_rebuild()
Ont00000223.model_rebuild()
Ont00000253.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b10.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b14.model_rebuild()
Ont00000314.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b19.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b23.model_rebuild()
Ont00000498.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b27.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b31.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b35.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b40.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b47.model_rebuild()
Ont00000958.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b51.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b55.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b59.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b63.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b67.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b71.model_rebuild()
N2bfb5da6e2194aa7ba47ffc474ebfe37b75.model_rebuild()
Ont00000686.model_rebuild()
Ont00000853.model_rebuild()
Ont00000965.model_rebuild()
Ont00001069.model_rebuild()
Ont00002001.model_rebuild()
Ont00000003.model_rebuild()
Ont00000120.model_rebuild()
Ont00000127.model_rebuild()
Ont00000390.model_rebuild()
Ont00000398.model_rebuild()
Ont00000399.model_rebuild()
Ont00000626.model_rebuild()
Ont00000649.model_rebuild()
Ont00000653.model_rebuild()
Ont00001163.model_rebuild()
Ont00001175.model_rebuild()
Ont00002002.model_rebuild()
Ont00002004.model_rebuild()
Ont00002006.model_rebuild()
Ont00002007.model_rebuild()
Ont00002009.model_rebuild()
Ont00002010.model_rebuild()
Ont00002014.model_rebuild()
Ont00002037.model_rebuild()
Ont00002038.model_rebuild()
Ont00002039.model_rebuild()
Ont00000073.model_rebuild()
Ont00000077.model_rebuild()
Ont00000146.model_rebuild()
Ont00000275.model_rebuild()
Ont00000293.model_rebuild()
Ont00000406.model_rebuild()
Ont00000496.model_rebuild()
Ont00000540.model_rebuild()
Ont00000592.model_rebuild()
Ont00000605.model_rebuild()
Ont00000692.model_rebuild()
Ont00000731.model_rebuild()
Ont00000829.model_rebuild()
Ont00000923.model_rebuild()
Ont00000990.model_rebuild()
Ont00001010.model_rebuild()
Ont00001014.model_rebuild()
Ont00001022.model_rebuild()
Ont00001176.model_rebuild()
Ont00001205.model_rebuild()
Ont00001256.model_rebuild()
Ont00001328.model_rebuild()
Ont00001364.model_rebuild()
Ont00002003.model_rebuild()
Ont00002005.model_rebuild()
Ont00002008.model_rebuild()
Ont00002011.model_rebuild()
Ont00002012.model_rebuild()
Ont00002013.model_rebuild()
Ont00002015.model_rebuild()
Ont00002020.model_rebuild()
Ont00002040.model_rebuild()
Ont00002041.model_rebuild()
Ont00002042.model_rebuild()
Ont00002043.model_rebuild()
Ont00002044.model_rebuild()
Ont00002045.model_rebuild()
Ont00000067.model_rebuild()
Ont00000124.model_rebuild()
Ont00000164.model_rebuild()
Ont00000186.model_rebuild()
Ont00000203.model_rebuild()
Ont00000263.model_rebuild()
Ont00000369.model_rebuild()
Ont00000419.model_rebuild()
Ont00000469.model_rebuild()
Ont00000529.model_rebuild()
Ont00000539.model_rebuild()
Ont00000604.model_rebuild()
Ont00000669.model_rebuild()
Ont00000683.model_rebuild()
Ont00000729.model_rebuild()
Ont00000735.model_rebuild()
Ont00000745.model_rebuild()
Ont00000827.model_rebuild()
Ont00000845.model_rebuild()
Ont00000891.model_rebuild()
Ont00000915.model_rebuild()
Ont00001041.model_rebuild()
Ont00001101.model_rebuild()
Ont00001146.model_rebuild()
Ont00001235.model_rebuild()
Ont00001238.model_rebuild()
Ont00001309.model_rebuild()
Ont00001331.model_rebuild()
Ont00001351.model_rebuild()
Ont00001352.model_rebuild()
Ont00002016.model_rebuild()
Ont00002017.model_rebuild()
Ont00002018.model_rebuild()
Ont00002019.model_rebuild()
Ont00002021.model_rebuild()
Ont00002022.model_rebuild()
Ont00002023.model_rebuild()
Ont00002024.model_rebuild()
Ont00002025.model_rebuild()
Ont00002031.model_rebuild()
Ont00002032.model_rebuild()
Ont00002033.model_rebuild()
Ont00002034.model_rebuild()
Ont00000029.model_rebuild()
Ont00000080.model_rebuild()
Ont00000154.model_rebuild()
Ont00000276.model_rebuild()
Ont00000630.model_rebuild()
Ont00000894.model_rebuild()
Ont00000896.model_rebuild()
Ont00000916.model_rebuild()
Ont00000973.model_rebuild()
Ont00001149.model_rebuild()
Ont00001340.model_rebuild()
Ont00002026.model_rebuild()
Ont00002027.model_rebuild()
Ont00002028.model_rebuild()
Ont00002029.model_rebuild()
Ont00002030.model_rebuild()
Ont00002035.model_rebuild()
Ont00002036.model_rebuild()
Ont00000087.model_rebuild()
Ont00000589.model_rebuild()
Ont00000749.model_rebuild()
Ont00000833.model_rebuild()
