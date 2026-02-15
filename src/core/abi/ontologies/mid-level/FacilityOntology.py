from __future__ import annotations
from typing import ClassVar
from pydantic import BaseModel
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


class Ont00000192(RDFEntity):
    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000192'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000052(Ont00000192, RDFEntity):
    """
    Religious Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000052'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000055(Ont00000192, RDFEntity):
    """
    Healthcare Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000055'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000226(Ont00000192, RDFEntity):
    """
    Transportation Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000226'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000270(Ont00000192, RDFEntity):
    """
    Educational Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000270'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000332(Ont00000192, RDFEntity):
    """
    Training Camp
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000332'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000339(Ont00000192, RDFEntity):
    """
    Agricultural Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000339'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000410(Ont00000192, RDFEntity):
    """
    Residential Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000410'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000479(Ont00000192, RDFEntity):
    """
    Public Safety Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000479'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000531(Ont00000192, RDFEntity):
    """
    Communications Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000531'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000639(Ont00000192, RDFEntity):
    """
    Mine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000639'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000641(Ont00000192, RDFEntity):
    """
    Entertainment Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000641'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000655(Ont00000192, RDFEntity):
    """
    Mailing Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000655'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000677(Ont00000192, RDFEntity):
    """
    Product Transport Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000677'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000782(Ont00000192, RDFEntity):
    """
    Factory
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000782'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000814(Ont00000192, RDFEntity):
    """
    Water Treatment Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000814'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000881(Ont00000192, RDFEntity):
    """
    Storage Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000881'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000946(Ont00000192, RDFEntity):
    """
    Government Building
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000946'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001052(Ont00000192, RDFEntity):
    """
    Military Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001052'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001076(Ont00000192, RDFEntity):
    """
    Electric Power Station
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001076'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001102(Ont00000192, RDFEntity):
    """
    Commercial Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001102'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001287(Ont00000192, RDFEntity):
    """
    Maintenance Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001287'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001295(Ont00000192, RDFEntity):
    """
    Financial Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001295'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001315(Ont00000192, RDFEntity):
    """
    Waste Management Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001315'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001375(Ont00000192, RDFEntity):
    """
    Washing Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001375'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000032(Ont00000052, RDFEntity):
    """
    Church
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000032'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000040(Ont00001102, RDFEntity):
    """
    Grocery Store
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000040'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000041(Ont00000410, RDFEntity):
    """
    Hostel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000041'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000045(Ont00000881, RDFEntity):
    """
    Petroleum Depot
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000045'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000060(Ont00000639, RDFEntity):
    """
    Open Pit Mine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000060'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000094(Ont00000946, RDFEntity):
    """
    Seat of National Government
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000094'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000104(Ont00000639, RDFEntity):
    """
    Underwater Mine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000104'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000108(Ont00000226, RDFEntity):
    """
    Rail Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000108'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000180(Ont00000410, RDFEntity):
    """
    Hotel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000180'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000220(Ont00000881, RDFEntity):
    """
    Ammunition Depot
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000220'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000232(Ont00000677, RDFEntity):
    """
    Pumping Station
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000232'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000245(Ont00000782, RDFEntity):
    """
    Petroleum Manufacturing Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000245'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000248(Ont00000782, RDFEntity):
    """
    Chemical Manufacturing Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000248'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000262(Ont00001102, RDFEntity):
    """
    Shop
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000262'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000271(Ont00000639, RDFEntity):
    """
    Underground Mine
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000271'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000330(Ont00001076, RDFEntity):
    """
    Thermal Power Plant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000330'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000331(Ont00000410, RDFEntity):
    """
    House
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000331'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000336(Ont00000410, RDFEntity):
    """
    Apartment Building
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000336'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000349(Ont00000479, RDFEntity):
    """
    Police Station
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000349'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000375(Ont00000881, RDFEntity):
    """
    Warehouse
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000375'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000381(Ont00000782, RDFEntity):
    """
    Weapon Manufacturing Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000381'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000423(Ont00000782, RDFEntity):
    """
    Motor Vehicle Manufacturing Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000423'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000432(Ont00001052, RDFEntity):
    """
    Missile Launch Site
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000432'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000468(Ont00001102, RDFEntity):
    """
    Office Building
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000468'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000483(Ont00001052, RDFEntity):
    """
    Military Base
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000483'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000510(Ont00000052, RDFEntity):
    """
    Mosque
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000510'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000545(Ont00000946, RDFEntity):
    """
    Seat of Local Government
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000545'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000664(Ont00000531, RDFEntity):
    """
    Radio Relay Station
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000664'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000667(Ont00001052, RDFEntity):
    """
    Combat Outpost
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000667'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000680(Ont00000881, RDFEntity):
    """
    Medical Depot
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000680'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000705(Ont00000677, RDFEntity):
    """
    Power Transmission Line
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000705'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000708(Ont00000881, RDFEntity):
    """
    Water Tower
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000708'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000710(Ont00001052, RDFEntity):
    """
    Command Post Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000710'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000717(Ont00001076, RDFEntity):
    """
    Fossil Fuel Power Plant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000717'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000757(Ont00000052, RDFEntity):
    """
    Synagogue
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000757'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000761(Ont00000226, RDFEntity):
    """
    Pier
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000761'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000778(Ont00000881, RDFEntity):
    """
    Chemical Depot
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000778'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000802(Ont00000641, RDFEntity):
    """
    Stage
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000802'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000846(Ont00001076, RDFEntity):
    """
    Hydroelectric Power Plant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000846'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000867(Ont00000677, RDFEntity):
    """
    Pipeline
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000867'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000882(Ont00001076, RDFEntity):
    """
    Wind Farm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000882'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000901(Ont00001375, RDFEntity):
    """
    Decontamination Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000901'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000905(Ont00000655, RDFEntity):
    """
    Post Office
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000905'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000957(Ont00000881, RDFEntity):
    """
    Reservoir
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000957'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001078(Ont00000226, RDFEntity):
    """
    Airport
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001078'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001091(Ont00001052, RDFEntity):
    """
    Fort
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001091'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001098(Ont00000055, RDFEntity):
    """
    Hospital
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001098'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001107(Ont00001315, RDFEntity):
    """
    Landfill
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001107'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001165(Ont00000332, RDFEntity):
    """
    Terrorist Training Camp
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001165'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001257(Ont00000881, RDFEntity):
    """
    Nuclear Storage Depot
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001257'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001258(Ont00000226, RDFEntity):
    """
    Port
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001258'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001283(Ont00000782, RDFEntity):
    """
    Refinery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001283'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001297(Ont00001052, RDFEntity):
    """
    Military Headquarters Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001297'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001308(Ont00001315, RDFEntity):
    """
    Sewage Treatment Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001308'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001311(Ont00000782, RDFEntity):
    """
    Aircraft Manufacturing Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001311'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001344(Ont00000881, RDFEntity):
    """
    Biological Depot
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001344'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001358(Ont00000270, RDFEntity):
    """
    School
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001358'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001380(Ont00000339, RDFEntity):
    """
    Farm
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001380'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001383(Ont00000479, RDFEntity):
    """
    Fire Station
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001383'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000172(Ont00000483, RDFEntity):
    """
    Base of Operations
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000172'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000195(Ont00001078, RDFEntity):
    """
    Heliport
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000195'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000421(Ont00000330, RDFEntity):
    """
    Nuclear Power Plant
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000421'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000583(Ont00000180, RDFEntity):
    """
    Motel
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000583'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000670(Ont00001258, RDFEntity):
    """
    Distribution Port
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000670'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00000737(Ont00000483, RDFEntity):
    """
    Forward Operations Base
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00000737'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001089(Ont00001283, RDFEntity):
    """
    Petrochemical Refinery
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001089'
    _property_uris: ClassVar[dict] = {}
    pass

class Ont00001362(Ont00001283, RDFEntity):
    """
    Gas Processing Facility
    """

    _class_uri: ClassVar[str] = 'https://www.commoncoreontologies.org/ont00001362'
    _property_uris: ClassVar[dict] = {}
    pass

# Rebuild models to resolve forward references
Ont00000192.model_rebuild()
Ont00000052.model_rebuild()
Ont00000055.model_rebuild()
Ont00000226.model_rebuild()
Ont00000270.model_rebuild()
Ont00000332.model_rebuild()
Ont00000339.model_rebuild()
Ont00000410.model_rebuild()
Ont00000479.model_rebuild()
Ont00000531.model_rebuild()
Ont00000639.model_rebuild()
Ont00000641.model_rebuild()
Ont00000655.model_rebuild()
Ont00000677.model_rebuild()
Ont00000782.model_rebuild()
Ont00000814.model_rebuild()
Ont00000881.model_rebuild()
Ont00000946.model_rebuild()
Ont00001052.model_rebuild()
Ont00001076.model_rebuild()
Ont00001102.model_rebuild()
Ont00001287.model_rebuild()
Ont00001295.model_rebuild()
Ont00001315.model_rebuild()
Ont00001375.model_rebuild()
Ont00000032.model_rebuild()
Ont00000040.model_rebuild()
Ont00000041.model_rebuild()
Ont00000045.model_rebuild()
Ont00000060.model_rebuild()
Ont00000094.model_rebuild()
Ont00000104.model_rebuild()
Ont00000108.model_rebuild()
Ont00000180.model_rebuild()
Ont00000220.model_rebuild()
Ont00000232.model_rebuild()
Ont00000245.model_rebuild()
Ont00000248.model_rebuild()
Ont00000262.model_rebuild()
Ont00000271.model_rebuild()
Ont00000330.model_rebuild()
Ont00000331.model_rebuild()
Ont00000336.model_rebuild()
Ont00000349.model_rebuild()
Ont00000375.model_rebuild()
Ont00000381.model_rebuild()
Ont00000423.model_rebuild()
Ont00000432.model_rebuild()
Ont00000468.model_rebuild()
Ont00000483.model_rebuild()
Ont00000510.model_rebuild()
Ont00000545.model_rebuild()
Ont00000664.model_rebuild()
Ont00000667.model_rebuild()
Ont00000680.model_rebuild()
Ont00000705.model_rebuild()
Ont00000708.model_rebuild()
Ont00000710.model_rebuild()
Ont00000717.model_rebuild()
Ont00000757.model_rebuild()
Ont00000761.model_rebuild()
Ont00000778.model_rebuild()
Ont00000802.model_rebuild()
Ont00000846.model_rebuild()
Ont00000867.model_rebuild()
Ont00000882.model_rebuild()
Ont00000901.model_rebuild()
Ont00000905.model_rebuild()
Ont00000957.model_rebuild()
Ont00001078.model_rebuild()
Ont00001091.model_rebuild()
Ont00001098.model_rebuild()
Ont00001107.model_rebuild()
Ont00001165.model_rebuild()
Ont00001257.model_rebuild()
Ont00001258.model_rebuild()
Ont00001283.model_rebuild()
Ont00001297.model_rebuild()
Ont00001308.model_rebuild()
Ont00001311.model_rebuild()
Ont00001344.model_rebuild()
Ont00001358.model_rebuild()
Ont00001380.model_rebuild()
Ont00001383.model_rebuild()
Ont00000172.model_rebuild()
Ont00000195.model_rebuild()
Ont00000421.model_rebuild()
Ont00000583.model_rebuild()
Ont00000670.model_rebuild()
Ont00000737.model_rebuild()
Ont00001089.model_rebuild()
Ont00001362.model_rebuild()
