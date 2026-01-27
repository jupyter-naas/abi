from __future__ import annotations

import uuid
from typing import ClassVar, Optional, Union

from pydantic import BaseModel, Field
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

# Generated classes from TTL file


# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""

    _namespace: ClassVar[str] = "http://example.org/instance/"
    _uri: str = ""
    _object_properties: ClassVar[set[str]] = set()

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}

    def __init__(self, **kwargs):
        uri = kwargs.pop("_uri", None)
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
        if hasattr(self, "_class_uri"):
            g.add((subject, RDF.type, URIRef(self._class_uri)))

        object_props: set[str] = getattr(self, "_object_properties", set())

        # Add properties
        if hasattr(self, "_property_uris"):
            for prop_name, prop_uri in self._property_uris.items():
                is_object_prop = prop_name in object_props
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, "rdf"):
                                # Add triples from related object
                                g += item.rdf()
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            elif is_object_prop and isinstance(item, (str, URIRef)):
                                g.add((subject, URIRef(prop_uri), URIRef(str(item))))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, "rdf"):
                        # Add triples from related object
                        g += prop_value.rdf()
                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))
                    elif is_object_prop and isinstance(prop_value, (str, URIRef)):
                        g.add((subject, URIRef(prop_uri), URIRef(str(prop_value))))
                    else:
                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))

        return g


class Process(RDFEntity):
    """
    process
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000015"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "has_participant": "http://purl.obolibrary.org/obo/BFO_0000057",
        "occupies_temporal_region": "http://purl.obolibrary.org/obo/BFO_0000199",
        "occurs_in": "http://purl.obolibrary.org/obo/BFO_0000066",
        "realizes": "http://purl.obolibrary.org/obo/BFO_0000055",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_participant",
        "occupies_temporal_region",
        "occurs_in",
        "realizes",
    }

    # Object properties
    concretizes: Optional[Union[str, GenericallyDependentContinuant]] = Field(
        description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
    )
    has_participant: Optional[Union[str, MaterialEntity, Quality]] = Field(
        description="p has participant c =Def c participates in p"
    )
    occupies_temporal_region: Optional[Union[str, TemporalRegion]] = Field(
        description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
    )
    occurs_in: Optional[Union[str, Site]] = Field(
        description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
    )
    realizes: Optional[Union[str, Role, Disposition]] = Field(
        description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
    )


class TemporalRegion(RDFEntity):
    """
    temporal region
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000008"
    _property_uris: ClassVar[dict] = {}
    _object_properties: ClassVar[set[str]] = set()

    pass


class MaterialEntity(RDFEntity):
    """
    material entity
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000040"
    _property_uris: ClassVar[dict] = {
        "bearer_of": "http://purl.obolibrary.org/obo/BFO_0000196",
        "has_member_part": "http://purl.obolibrary.org/obo/BFO_0000115",
        "is_carrier_of": "http://purl.obolibrary.org/obo/BFO_0000101",
        "located_in": "http://purl.obolibrary.org/obo/BFO_0000171",
        "material_basis_of": "http://purl.obolibrary.org/obo/BFO_0000127",
        "participates_in": "http://purl.obolibrary.org/obo/BFO_0000056",
    }
    _object_properties: ClassVar[set[str]] = {
        "bearer_of",
        "has_member_part",
        "is_carrier_of",
        "located_in",
        "material_basis_of",
        "participates_in",
    }

    # Object properties
    bearer_of: Optional[Union[str, Quality, Role, Disposition]] = Field(
        description="b bearer of c =Def c inheres in b"
    )
    has_member_part: Optional[Union[str, MaterialEntity]] = Field(
        description="b has member part c =Def c member part of b"
    )
    is_carrier_of: Optional[Union[str, GenericallyDependentContinuant]] = Field(
        description="b is carrier of c =Def there is some time t such that c generically depends on b at t"
    )
    located_in: Optional[Union[str, Site]] = Field(
        description="b located in c =Def b is an independent continuant & c is an independent & neither is a spatial region & there is some time t such that the spatial region which b occupies at t is continuant part of the spatial region which c occupies at t"
    )
    material_basis_of: Optional[Union[str, Disposition]] = Field(
        description="b material basis of c =Def c has material basis b"
    )
    participates_in: Optional[Union[str, Process]] = Field(
        description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
    )


class Site(RDFEntity):
    """
    site
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000029"
    _property_uris: ClassVar[dict] = {}
    _object_properties: ClassVar[set[str]] = set()

    pass


class GenericallyDependentContinuant(RDFEntity):
    """
    generically dependent continuant
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000031"
    _property_uris: ClassVar[dict] = {
        "generically_depends_on": "http://purl.obolibrary.org/obo/BFO_0000084",
        "is_concretized_by": "http://purl.obolibrary.org/obo/BFO_0000058",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
    }

    # Object properties
    generically_depends_on: Optional[Union[str, MaterialEntity]] = Field(
        description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
    )
    is_concretized_by: Optional[Union[str, Process, Quality, Role, Disposition]] = (
        Field(description="c is concretized by b =Def b concretizes c")
    )


class Quality(RDFEntity):
    """
    quality
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000019"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
        "participates_in": "http://purl.obolibrary.org/obo/BFO_0000056",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "inheres_in",
        "participates_in",
    }

    # Object properties
    concretizes: Optional[Union[str, GenericallyDependentContinuant]] = Field(
        description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
    )
    inheres_in: Optional[Union[str, MaterialEntity]] = Field(
        description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
    )
    participates_in: Optional[Union[str, Process]] = Field(
        description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
    )


class Role(RDFEntity):
    """
    role
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000023"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "has_realization": "http://purl.obolibrary.org/obo/BFO_0000054",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
    }

    # Object properties
    concretizes: Optional[Union[str, GenericallyDependentContinuant]] = Field(
        description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
    )
    has_realization: Optional[Union[str, Process]] = Field(
        description="b has realization c =Def c realizes b"
    )
    inheres_in: Optional[Union[str, MaterialEntity]] = Field(
        description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
    )


class Disposition(RDFEntity):
    """
    disposition
    """

    _class_uri: ClassVar[str] = "http://purl.obolibrary.org/obo/BFO_0000016"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "has_material_basis": "http://purl.obolibrary.org/obo/BFO_0000218",
        "has_realization": "http://purl.obolibrary.org/obo/BFO_0000054",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_material_basis",
        "has_realization",
    }

    # Object properties
    concretizes: Optional[Union[str, GenericallyDependentContinuant]] = Field(
        description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
    )
    has_material_basis: Optional[Union[str, MaterialEntity]] = Field(
        description="b has material basis c =Def b is a disposition & c is a material entity & there is some d bearer of b & there is some time t such that c is a continuant part of d at t & d has disposition b because c is a continuant part of d at t"
    )
    has_realization: Optional[Union[str, Process]] = Field(
        description="b has realization c =Def c realizes b"
    )


# Rebuild models to resolve forward references
Process.model_rebuild()
TemporalRegion.model_rebuild()
MaterialEntity.model_rebuild()
Site.model_rebuild()
GenericallyDependentContinuant.model_rebuild()
Quality.model_rebuild()
Role.model_rebuild()
Disposition.model_rebuild()
