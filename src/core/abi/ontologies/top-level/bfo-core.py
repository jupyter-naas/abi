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


class N6253bef5339f439886c7fe9074b8a495b1(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b1'
    _property_uris: ClassVar[dict] = {'bFO_0000056': 'http://purl.obolibrary.org/obo/BFO_0000056'}

    # Object properties
    bFO_0000056: Optional[BFO_0000015] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b3(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b3'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b2(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b2'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b9(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b9'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b11(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b11'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b10(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b10'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b17(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b17'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b20(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b20'
    _property_uris: ClassVar[dict] = {'bFO_0000059': 'http://purl.obolibrary.org/obo/BFO_0000059'}

    # Object properties
    bFO_0000059: Optional[BFO_0000031] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b23(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b23'
    _property_uris: ClassVar[dict] = {'bFO_0000066': 'http://purl.obolibrary.org/obo/BFO_0000066'}

    # Object properties
    bFO_0000066: Optional[N6253bef5339f439886c7fe9074b8a495b26] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b26(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b26'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b30(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b30'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b29(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b29'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b34(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b34'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b33(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b33'
    _property_uris: ClassVar[dict] = {'bFO_0000101': 'http://purl.obolibrary.org/obo/BFO_0000101'}

    # Object properties
    bFO_0000101: Optional[BFO_0000031] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b38(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b38'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b37(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b37'
    _property_uris: ClassVar[dict] = {'bFO_0000124': 'http://purl.obolibrary.org/obo/BFO_0000124'}

    # Object properties
    bFO_0000124: Optional[N6253bef5339f439886c7fe9074b8a495b41] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b42(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b42'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b41(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b41'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b46(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b46'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b45(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b45'
    _property_uris: ClassVar[dict] = {'bFO_0000171': 'http://purl.obolibrary.org/obo/BFO_0000171'}

    # Object properties
    bFO_0000171: Optional[N6253bef5339f439886c7fe9074b8a495b49] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b50(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b50'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b49(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b49'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b53(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b53'
    _property_uris: ClassVar[dict] = {'bFO_0000183': 'http://purl.obolibrary.org/obo/BFO_0000183'}

    # Object properties
    bFO_0000183: Optional[N6253bef5339f439886c7fe9074b8a495b56] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b56(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b56'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b59(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b59'
    _property_uris: ClassVar[dict] = {'bFO_0000194': 'http://purl.obolibrary.org/obo/BFO_0000194'}

    # Object properties
    bFO_0000194: Optional[BFO_0000020] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b61(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b61'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b60(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b60'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b66(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b66'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b68(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b68'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b67(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b67'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b74(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b74'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b73(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b73'
    _property_uris: ClassVar[dict] = {'bFO_0000196': 'http://purl.obolibrary.org/obo/BFO_0000196'}

    # Object properties
    bFO_0000196: Optional[BFO_0000020] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b78(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b78'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b77(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b77'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b81(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b81'
    _property_uris: ClassVar[dict] = {'bFO_0000199': 'http://purl.obolibrary.org/obo/BFO_0000199'}

    # Object properties
    bFO_0000199: Optional[BFO_0000008] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b84(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b84'
    _property_uris: ClassVar[dict] = {'bFO_0000200': 'http://purl.obolibrary.org/obo/BFO_0000200'}

    # Object properties
    bFO_0000200: Optional[BFO_0000011] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b88(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b88'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b87(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b87'
    _property_uris: ClassVar[dict] = {'bFO_0000210': 'http://purl.obolibrary.org/obo/BFO_0000210'}

    # Object properties
    bFO_0000210: Optional[BFO_0000006] = Field(default=None)

class BFO_0000001(RDFEntity):
    """
    entity
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000001'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)

class N6253bef5339f439886c7fe9074b8a495b97(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b97'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b104(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b104'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b111(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b111'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b116(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b116'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b120(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b120'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b127(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b127'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b131(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b131'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b135(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b135'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b141(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b141'
    _property_uris: ClassVar[dict] = {}
    pass

class N6253bef5339f439886c7fe9074b8a495b148(RDFEntity):
    _class_uri: ClassVar[str] = 'n6253bef5339f439886c7fe9074b8a495b148'
    _property_uris: ClassVar[dict] = {}
    pass

class BFO_0000002(BFO_0000001, RDFEntity):
    """
    continuant
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000002'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000003(BFO_0000001, RDFEntity):
    """
    occurrent
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000003'
    _property_uris: ClassVar[dict] = {'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139'}

    # Object properties
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)

class BFO_0000004(BFO_0000002, RDFEntity):
    """
    independent continuant
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000004'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000008(BFO_0000003, RDFEntity):
    """
    temporal region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000008'
    _property_uris: ClassVar[dict] = {'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139', 'bFO_0000222': 'http://purl.obolibrary.org/obo/BFO_0000222', 'bFO_0000224': 'http://purl.obolibrary.org/obo/BFO_0000224'}

    # Object properties
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)
    bFO_0000222: Optional[BFO_0000203] = Field(default=None)
    bFO_0000224: Optional[BFO_0000203] = Field(default=None)

class BFO_0000011(BFO_0000003, RDFEntity):
    """
    spatiotemporal region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000011'
    _property_uris: ClassVar[dict] = {'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139', 'bFO_0000153': 'http://purl.obolibrary.org/obo/BFO_0000153', 'bFO_0000216': 'http://purl.obolibrary.org/obo/BFO_0000216'}

    # Object properties
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)
    bFO_0000153: Optional[BFO_0000008] = Field(default=None)
    bFO_0000216: Optional[BFO_0000006] = Field(default=None)

class BFO_0000015(BFO_0000003, RDFEntity):
    """
    process
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000015'
    _property_uris: ClassVar[dict] = {'bFO_0000055': 'http://purl.obolibrary.org/obo/BFO_0000055', 'bFO_0000057': 'http://purl.obolibrary.org/obo/BFO_0000057', 'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139'}

    # Object properties
    bFO_0000055: Optional[BFO_0000017] = Field(default=None)
    bFO_0000057: Optional[N6253bef5339f439886c7fe9074b8a495b9] = Field(default=None)
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)

class BFO_0000020(BFO_0000002, RDFEntity):
    """
    specifically dependent continuant
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000020'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000195': 'http://purl.obolibrary.org/obo/BFO_0000195', 'bFO_0000197': 'http://purl.obolibrary.org/obo/BFO_0000197'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000195: Optional[N6253bef5339f439886c7fe9074b8a495b66] = Field(default=None)
    bFO_0000197: Optional[N6253bef5339f439886c7fe9074b8a495b77] = Field(default=None)

class BFO_0000031(BFO_0000002, RDFEntity):
    """
    generically dependent continuant
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000031'
    _property_uris: ClassVar[dict] = {'bFO_0000058': 'http://purl.obolibrary.org/obo/BFO_0000058', 'bFO_0000084': 'http://purl.obolibrary.org/obo/BFO_0000084', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000058: Optional[N6253bef5339f439886c7fe9074b8a495b17] = Field(default=None)
    bFO_0000084: Optional[N6253bef5339f439886c7fe9074b8a495b29] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000035(BFO_0000003, RDFEntity):
    """
    process boundary
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000035'
    _property_uris: ClassVar[dict] = {'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139'}

    # Object properties
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)

class BFO_0000017(BFO_0000020, RDFEntity):
    """
    realizable entity
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000017'
    _property_uris: ClassVar[dict] = {'bFO_0000054': 'http://purl.obolibrary.org/obo/BFO_0000054', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000195': 'http://purl.obolibrary.org/obo/BFO_0000195', 'bFO_0000197': 'http://purl.obolibrary.org/obo/BFO_0000197'}

    # Object properties
    bFO_0000054: Optional[BFO_0000015] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000195: Optional[N6253bef5339f439886c7fe9074b8a495b66] = Field(default=None)
    bFO_0000197: Optional[N6253bef5339f439886c7fe9074b8a495b77] = Field(default=None)

class BFO_0000019(BFO_0000020, RDFEntity):
    """
    quality
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000019'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000195': 'http://purl.obolibrary.org/obo/BFO_0000195', 'bFO_0000197': 'http://purl.obolibrary.org/obo/BFO_0000197'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000195: Optional[N6253bef5339f439886c7fe9074b8a495b66] = Field(default=None)
    bFO_0000197: Optional[N6253bef5339f439886c7fe9074b8a495b77] = Field(default=None)

class BFO_0000038(BFO_0000008, RDFEntity):
    """
    one-dimensional temporal region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000038'
    _property_uris: ClassVar[dict] = {'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139', 'bFO_0000222': 'http://purl.obolibrary.org/obo/BFO_0000222', 'bFO_0000224': 'http://purl.obolibrary.org/obo/BFO_0000224'}

    # Object properties
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)
    bFO_0000222: Optional[BFO_0000203] = Field(default=None)
    bFO_0000224: Optional[BFO_0000203] = Field(default=None)

class BFO_0000040(BFO_0000004, RDFEntity):
    """
    material entity
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000040'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000115': 'http://purl.obolibrary.org/obo/BFO_0000115', 'bFO_0000127': 'http://purl.obolibrary.org/obo/BFO_0000127', 'bFO_0000129': 'http://purl.obolibrary.org/obo/BFO_0000129', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000185': 'http://purl.obolibrary.org/obo/BFO_0000185'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000115: Optional[BFO_0000040] = Field(default=None)
    bFO_0000127: Optional[BFO_0000016] = Field(default=None)
    bFO_0000129: Optional[BFO_0000040] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000185: Optional[BFO_0000182] = Field(default=None)

class BFO_0000141(BFO_0000004, RDFEntity):
    """
    immaterial entity
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000141'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000148(BFO_0000008, RDFEntity):
    """
    zero-dimensional temporal region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000148'
    _property_uris: ClassVar[dict] = {'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139', 'bFO_0000222': 'http://purl.obolibrary.org/obo/BFO_0000222', 'bFO_0000224': 'http://purl.obolibrary.org/obo/BFO_0000224'}

    # Object properties
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)
    bFO_0000222: Optional[BFO_0000203] = Field(default=None)
    bFO_0000224: Optional[BFO_0000203] = Field(default=None)

class BFO_0000182(BFO_0000015, RDFEntity):
    """
    history
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000182'
    _property_uris: ClassVar[dict] = {'bFO_0000055': 'http://purl.obolibrary.org/obo/BFO_0000055', 'bFO_0000057': 'http://purl.obolibrary.org/obo/BFO_0000057', 'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139', 'bFO_0000184': 'http://purl.obolibrary.org/obo/BFO_0000184'}

    # Object properties
    bFO_0000055: Optional[BFO_0000017] = Field(default=None)
    bFO_0000057: Optional[N6253bef5339f439886c7fe9074b8a495b9] = Field(default=None)
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)
    bFO_0000184: Optional[BFO_0000040] = Field(default=None)

class BFO_0000006(BFO_0000141, RDFEntity):
    """
    spatial region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000006'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000016(BFO_0000017, RDFEntity):
    """
    disposition
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000016'
    _property_uris: ClassVar[dict] = {'bFO_0000054': 'http://purl.obolibrary.org/obo/BFO_0000054', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000195': 'http://purl.obolibrary.org/obo/BFO_0000195', 'bFO_0000197': 'http://purl.obolibrary.org/obo/BFO_0000197', 'bFO_0000218': 'http://purl.obolibrary.org/obo/BFO_0000218'}

    # Object properties
    bFO_0000054: Optional[BFO_0000015] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000195: Optional[N6253bef5339f439886c7fe9074b8a495b66] = Field(default=None)
    bFO_0000197: Optional[N6253bef5339f439886c7fe9074b8a495b77] = Field(default=None)
    bFO_0000218: Optional[BFO_0000040] = Field(default=None)

class BFO_0000023(BFO_0000017, RDFEntity):
    """
    role
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000023'
    _property_uris: ClassVar[dict] = {'bFO_0000054': 'http://purl.obolibrary.org/obo/BFO_0000054', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000195': 'http://purl.obolibrary.org/obo/BFO_0000195', 'bFO_0000197': 'http://purl.obolibrary.org/obo/BFO_0000197'}

    # Object properties
    bFO_0000054: Optional[BFO_0000015] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000195: Optional[N6253bef5339f439886c7fe9074b8a495b66] = Field(default=None)
    bFO_0000197: Optional[N6253bef5339f439886c7fe9074b8a495b77] = Field(default=None)

class BFO_0000024(BFO_0000040, RDFEntity):
    """
    fiat object part
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000024'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000115': 'http://purl.obolibrary.org/obo/BFO_0000115', 'bFO_0000127': 'http://purl.obolibrary.org/obo/BFO_0000127', 'bFO_0000129': 'http://purl.obolibrary.org/obo/BFO_0000129', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000185': 'http://purl.obolibrary.org/obo/BFO_0000185'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000115: Optional[BFO_0000040] = Field(default=None)
    bFO_0000127: Optional[BFO_0000016] = Field(default=None)
    bFO_0000129: Optional[BFO_0000040] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000185: Optional[BFO_0000182] = Field(default=None)

class BFO_0000027(BFO_0000040, RDFEntity):
    """
    object aggregate
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000027'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000115': 'http://purl.obolibrary.org/obo/BFO_0000115', 'bFO_0000127': 'http://purl.obolibrary.org/obo/BFO_0000127', 'bFO_0000129': 'http://purl.obolibrary.org/obo/BFO_0000129', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000185': 'http://purl.obolibrary.org/obo/BFO_0000185'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000115: Optional[BFO_0000040] = Field(default=None)
    bFO_0000127: Optional[BFO_0000016] = Field(default=None)
    bFO_0000129: Optional[BFO_0000040] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000185: Optional[BFO_0000182] = Field(default=None)

class BFO_0000029(BFO_0000141, RDFEntity):
    """
    site
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000029'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000030(BFO_0000040, RDFEntity):
    """
    object
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000030'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000115': 'http://purl.obolibrary.org/obo/BFO_0000115', 'bFO_0000127': 'http://purl.obolibrary.org/obo/BFO_0000127', 'bFO_0000129': 'http://purl.obolibrary.org/obo/BFO_0000129', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000185': 'http://purl.obolibrary.org/obo/BFO_0000185'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000115: Optional[BFO_0000040] = Field(default=None)
    bFO_0000127: Optional[BFO_0000016] = Field(default=None)
    bFO_0000129: Optional[BFO_0000040] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000185: Optional[BFO_0000182] = Field(default=None)

class BFO_0000140(BFO_0000141, RDFEntity):
    """
    continuant fiat boundary
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000140'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000145(BFO_0000019, RDFEntity):
    """
    relational quality
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000145'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000195': 'http://purl.obolibrary.org/obo/BFO_0000195', 'bFO_0000197': 'http://purl.obolibrary.org/obo/BFO_0000197'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000195: Optional[N6253bef5339f439886c7fe9074b8a495b66] = Field(default=None)
    bFO_0000197: Optional[N6253bef5339f439886c7fe9074b8a495b77] = Field(default=None)

class BFO_0000202(BFO_0000038, RDFEntity):
    """
    temporal interval
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000202'
    _property_uris: ClassVar[dict] = {'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139', 'bFO_0000222': 'http://purl.obolibrary.org/obo/BFO_0000222', 'bFO_0000224': 'http://purl.obolibrary.org/obo/BFO_0000224'}

    # Object properties
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)
    bFO_0000222: Optional[BFO_0000203] = Field(default=None)
    bFO_0000224: Optional[BFO_0000203] = Field(default=None)

class BFO_0000203(BFO_0000148, RDFEntity):
    """
    temporal instant
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000203'
    _property_uris: ClassVar[dict] = {'bFO_0000062': 'http://purl.obolibrary.org/obo/BFO_0000062', 'bFO_0000063': 'http://purl.obolibrary.org/obo/BFO_0000063', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000117': 'http://purl.obolibrary.org/obo/BFO_0000117', 'bFO_0000121': 'http://purl.obolibrary.org/obo/BFO_0000121', 'bFO_0000132': 'http://purl.obolibrary.org/obo/BFO_0000132', 'bFO_0000139': 'http://purl.obolibrary.org/obo/BFO_0000139', 'bFO_0000221': 'http://purl.obolibrary.org/obo/BFO_0000221', 'bFO_0000222': 'http://purl.obolibrary.org/obo/BFO_0000222', 'bFO_0000223': 'http://purl.obolibrary.org/obo/BFO_0000223', 'bFO_0000224': 'http://purl.obolibrary.org/obo/BFO_0000224'}

    # Object properties
    bFO_0000062: Optional[BFO_0000003] = Field(default=None)
    bFO_0000063: Optional[BFO_0000003] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000117: Optional[BFO_0000003] = Field(default=None)
    bFO_0000121: Optional[BFO_0000003] = Field(default=None)
    bFO_0000132: Optional[BFO_0000003] = Field(default=None)
    bFO_0000139: Optional[BFO_0000003] = Field(default=None)
    bFO_0000221: Optional[BFO_0000008] = Field(default=None)
    bFO_0000222: Optional[BFO_0000203] = Field(default=None)
    bFO_0000223: Optional[BFO_0000008] = Field(default=None)
    bFO_0000224: Optional[BFO_0000203] = Field(default=None)

class BFO_0000009(BFO_0000006, RDFEntity):
    """
    two-dimensional spatial region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000009'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000018(BFO_0000006, RDFEntity):
    """
    zero-dimensional spatial region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000018'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000026(BFO_0000006, RDFEntity):
    """
    one-dimensional spatial region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000026'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000028(BFO_0000006, RDFEntity):
    """
    three-dimensional spatial region
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000028'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000034(BFO_0000016, RDFEntity):
    """
    function
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000034'
    _property_uris: ClassVar[dict] = {'bFO_0000054': 'http://purl.obolibrary.org/obo/BFO_0000054', 'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178', 'bFO_0000195': 'http://purl.obolibrary.org/obo/BFO_0000195', 'bFO_0000197': 'http://purl.obolibrary.org/obo/BFO_0000197', 'bFO_0000218': 'http://purl.obolibrary.org/obo/BFO_0000218'}

    # Object properties
    bFO_0000054: Optional[BFO_0000015] = Field(default=None)
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)
    bFO_0000195: Optional[N6253bef5339f439886c7fe9074b8a495b66] = Field(default=None)
    bFO_0000197: Optional[N6253bef5339f439886c7fe9074b8a495b77] = Field(default=None)
    bFO_0000218: Optional[BFO_0000040] = Field(default=None)

class BFO_0000142(BFO_0000140, RDFEntity):
    """
    fiat line
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000142'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000146(BFO_0000140, RDFEntity):
    """
    fiat surface
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000146'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

class BFO_0000147(BFO_0000140, RDFEntity):
    """
    fiat point
    """

    _class_uri: ClassVar[str] = 'http://purl.obolibrary.org/obo/BFO_0000147'
    _property_uris: ClassVar[dict] = {'bFO_0000108': 'http://purl.obolibrary.org/obo/BFO_0000108', 'bFO_0000176': 'http://purl.obolibrary.org/obo/BFO_0000176', 'bFO_0000178': 'http://purl.obolibrary.org/obo/BFO_0000178'}

    # Object properties
    bFO_0000108: Optional[BFO_0000008] = Field(default=None)
    bFO_0000176: Optional[BFO_0000002] = Field(default=None)
    bFO_0000178: Optional[BFO_0000002] = Field(default=None)

# Rebuild models to resolve forward references
N6253bef5339f439886c7fe9074b8a495b1.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b3.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b2.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b9.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b11.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b10.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b17.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b20.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b23.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b26.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b30.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b29.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b34.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b33.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b38.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b37.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b42.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b41.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b46.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b45.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b50.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b49.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b53.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b56.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b59.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b61.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b60.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b66.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b68.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b67.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b74.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b73.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b78.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b77.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b81.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b84.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b88.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b87.model_rebuild()
BFO_0000001.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b97.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b104.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b111.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b116.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b120.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b127.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b131.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b135.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b141.model_rebuild()
N6253bef5339f439886c7fe9074b8a495b148.model_rebuild()
BFO_0000002.model_rebuild()
BFO_0000003.model_rebuild()
BFO_0000004.model_rebuild()
BFO_0000008.model_rebuild()
BFO_0000011.model_rebuild()
BFO_0000015.model_rebuild()
BFO_0000020.model_rebuild()
BFO_0000031.model_rebuild()
BFO_0000035.model_rebuild()
BFO_0000017.model_rebuild()
BFO_0000019.model_rebuild()
BFO_0000038.model_rebuild()
BFO_0000040.model_rebuild()
BFO_0000141.model_rebuild()
BFO_0000148.model_rebuild()
BFO_0000182.model_rebuild()
BFO_0000006.model_rebuild()
BFO_0000016.model_rebuild()
BFO_0000023.model_rebuild()
BFO_0000024.model_rebuild()
BFO_0000027.model_rebuild()
BFO_0000029.model_rebuild()
BFO_0000030.model_rebuild()
BFO_0000140.model_rebuild()
BFO_0000145.model_rebuild()
BFO_0000202.model_rebuild()
BFO_0000203.model_rebuild()
BFO_0000009.model_rebuild()
BFO_0000018.model_rebuild()
BFO_0000026.model_rebuild()
BFO_0000028.model_rebuild()
BFO_0000034.model_rebuild()
BFO_0000142.model_rebuild()
BFO_0000146.model_rebuild()
BFO_0000147.model_rebuild()
