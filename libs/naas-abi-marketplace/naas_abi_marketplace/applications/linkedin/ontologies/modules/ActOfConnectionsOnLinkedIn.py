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


class ActOfConnectionOnLinkedIn(RDFEntity):
    """
    Act of connection on LinkedIn
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ActOfConnection"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "connected_at": "http://ontology.naas.ai/abi/linkedin/connectedAt",
        "has_associated_linkedin_quality": "http://ontology.naas.ai/abi/linkedin/hasAssociatedQuality",
        "involves_agent": "http://ontology.naas.ai/abi/linkedin/involvesAgent",
        "occurs_in": "http://purl.obolibrary.org/obo/BFO_0000066",
        "realizes": "http://purl.obolibrary.org/obo/BFO_0000055",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "connected_at",
        "has_associated_linkedin_quality",
        "involves_agent",
        "occurs_in",
        "realizes",
    }

    # Object properties
    concretizes: Optional[Union[str, ConnectionsExportFile, LinkedInProfilePage]] = (
        Field(
            description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
        )
    )
    connected_at: Optional[Union[str, ISO8601UTCDateTime]] = Field(
        description="Relates an act of connection to the specific temporal entity at which that act of connection occurs or is realized."
    )
    has_associated_linkedin_quality: Optional[
        Union[
            str,
            LinkedInCurrentJobPosition,
            LinkedInCurrentOrganization,
            LinkedInCurrentPublicURL,
            LinkedInEmailAddress,
        ]
    ] = Field(
        description="Relates a process (such as an act of connection) to a LinkedIn quality (such as CurrentJobPosition, CurrentOrganization, CurrentPublicUrl, or EmailAddress) that inheres in a participant of the process. This property is used to associate any LinkedIn quality with a process, emphasizing that the quality is relevant to or contextualizes the process, even if it is not a direct participant but is borne by one."
    )
    involves_agent: Optional[Union[str, Person, Organization]] = Field(
        description="Relates an event (such as an act of connection) to an agent (person or organization) involved in it. If an event involves agent x, then x is actively participating or is otherwise involved in the event."
    )
    occurs_in: Optional[Union[str, LinkedInLocation]] = Field(
        description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
    )
    realizes: Optional[Union[str, LinkedInConnectionRole]] = Field(
        description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
    )


class ISO8601UTCDateTime(RDFEntity):
    """
    ISO 8601 UTC DateTime
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ISO8601UTCDateTime"
    _property_uris: ClassVar[dict] = {}
    _object_properties: ClassVar[set[str]] = set()

    pass


class Person(RDFEntity):
    """
    Person
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001262"
    _property_uris: ClassVar[dict] = {
        "agent_involved_in": "http://ontology.naas.ai/abi/linkedin/agentInvolvedIn",
        "has_linkedin_connection_role": "http://ontology.naas.ai/abi/linkedin/hasConnectionRole",
        "has_linkedin_current_job_position": "http://ontology.naas.ai/abi/linkedin/hasCurrentJobPosition",
        "has_linkedin_current_organization": "http://ontology.naas.ai/abi/linkedin/hasCurrentOrganization",
        "has_linkedin_email_address": "http://ontology.naas.ai/abi/linkedin/hasEmailAddress",
        "has_linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/hasCurrentPublicUrl",
        "is_located_in": "http://ontology.naas.ai/abi/linkedin/locatedIn",
        "is_owner_of": "http://ontology.naas.ai/abi/linkedin/isOwnerOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "agent_involved_in",
        "has_linkedin_connection_role",
        "has_linkedin_current_job_position",
        "has_linkedin_current_organization",
        "has_linkedin_email_address",
        "has_linkedin_public_url",
        "is_located_in",
        "is_owner_of",
    }

    # Object properties
    agent_involved_in: Optional[Union[str, ActOfConnectionOnLinkedIn]] = Field(
        description="Relates an agent (person or organization) to an event in which the agent is involved or participates."
    )
    has_linkedin_connection_role: Optional[Union[str, LinkedInConnectionRole]] = Field(
        description="A person has LinkedIn connection role y if and only if y is a ConnectionRole (a quality) that inheres in the person and expresses their role in a connection as recorded on LinkedIn. This property connects a Person to the specific role they hold in a connection, as indicated on their LinkedIn profile."
    )
    has_linkedin_current_job_position: Optional[
        Union[str, LinkedInCurrentJobPosition]
    ] = Field(
        description="A person has LinkedIn current job position y if and only if y is a CurrentJobPosition (a quality) that inheres in the person and expresses their present professional role or job title as recorded on LinkedIn. This property connects a Person to the specific professional position or title they currently hold, as indicated on their LinkedIn profile."
    )
    has_linkedin_current_organization: Optional[
        Union[str, LinkedInCurrentOrganization]
    ] = Field(
        description="A person has LinkedIn current organization y if and only if y is a CurrentOrganization (a quality) that inheres in the person and expresses their present place of employment or affiliation as recorded on LinkedIn. This property connects a Person to the specific organization they currently work for or are affiliated with, as indicated on their LinkedIn profile."
    )
    has_linkedin_email_address: Optional[Union[str, LinkedInEmailAddress]] = Field(
        description="A person has LinkedIn email address y if and only if y is an EmailAddress (a quality) that inheres in the person and expresses their email address as recorded on LinkedIn. This property connects a Person to the specific email address they have registered on their LinkedIn profile."
    )
    has_linkedin_public_url: Optional[Union[str, LinkedInCurrentPublicURL]] = Field(
        description="A person has LinkedIn public URL y if and only if y is a CurrentPublicUrl (a quality) that inheres in the person and expresses their public web address as recorded on LinkedIn. This property connects a Person to the specific public web address they have registered on their LinkedIn profile."
    )
    is_located_in: Optional[Union[str, LinkedInLocation]] = Field(
        description="A person is located in y if and only if y is a UserSite that represents the location associated with the person on LinkedIn. This property connects a Person to the LinkedIn user site they are located in as indicated on their LinkedIn profile."
    )
    is_owner_of: Optional[Union[str, LinkedInProfilePage]] = Field(
        description="b is owner of c =Def b is a material entity (e.g., person or organization), c is an Information Content Entity (generically dependent continuant), and b has ownership or control over c as information."
    )


class Organization(RDFEntity):
    """
    Organization
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001180"
    _property_uris: ClassVar[dict] = {
        "agent_involved_in": "http://ontology.naas.ai/abi/linkedin/agentInvolvedIn",
        "holds_linkedin_quality": "http://ontology.naas.ai/abi/linkedin/holdsQuality",
        "is_located_in": "http://ontology.naas.ai/abi/linkedin/locatedIn",
        "is_owner_of": "http://ontology.naas.ai/abi/linkedin/isOwnerOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "agent_involved_in",
        "holds_linkedin_quality",
        "is_located_in",
        "is_owner_of",
    }

    # Object properties
    agent_involved_in: Optional[Union[str, ActOfConnectionOnLinkedIn]] = Field(
        description="Relates an agent (person or organization) to an event in which the agent is involved or participates."
    )
    holds_linkedin_quality: Optional[Union[str, LinkedInCurrentOrganization]] = Field(
        description="A organization holds quality y if and only if y is a CurrentOrganization (a quality) that inheres in the organization and expresses a specific quality or characteristic as recorded on LinkedIn. This property connects a Organization to the specific quality or characteristic they hold that can be indicated on their LinkedIn organization page or on people's LinkedIn profile page who are part of the organization."
    )
    is_located_in: Optional[Union[str, LinkedInLocation]] = Field(
        description="A person is located in y if and only if y is a UserSite that represents the location associated with the person on LinkedIn. This property connects a Person to the LinkedIn user site they are located in as indicated on their LinkedIn profile."
    )
    is_owner_of: Optional[Union[str, ConnectionsExportFile]] = Field(
        description="b is owner of c =Def b is a material entity (e.g., person or organization), c is an Information Content Entity (generically dependent continuant), and b has ownership or control over c as information."
    )


class LinkedInLocation(RDFEntity):
    """
    LinkedIn Location
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Location"
    _property_uris: ClassVar[dict] = {}
    _object_properties: ClassVar[set[str]] = set()

    pass


class LinkedInProfilePage(RDFEntity):
    """
    A LinkedIn profile page must be registered in https://www.linkedin.com/in/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ProfilePage"
    _property_uris: ClassVar[dict] = {
        "bFO_0000058": "http://purl.obolibrary.org/obo/BFO_0000058",
        "is_owned_by": "http://ontology.naas.ai/abi/linkedin/isOwnedBy",
    }
    _object_properties: ClassVar[set[str]] = {"bFO_0000058", "is_owned_by"}

    # Object properties
    bFO_0000058: Optional[
        Union[
            str,
            ActOfConnectionOnLinkedIn,
            LinkedInCurrentJobPosition,
            LinkedInCurrentOrganization,
            LinkedInCurrentPublicURL,
            LinkedInEmailAddress,
            LinkedInConnectionRole,
        ]
    ] = Field()
    is_owned_by: Optional[Union[str, Person]] = Field(
        description="c is owned by b =Def c is an Information Content Entity (e.g., LinkedIn profile page) and b is the material entity that has ownership or control over c as information."
    )


class ConnectionsExportFile(RDFEntity):
    """
    Connections export file
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/ConnectionsExportFile"
    )
    _property_uris: ClassVar[dict] = {
        "is_owned_by": "http://ontology.naas.ai/abi/linkedin/isOwnedBy"
    }
    _object_properties: ClassVar[set[str]] = {"is_owned_by"}

    # Object properties
    is_owned_by: Optional[Union[str, Organization]] = Field(
        description="c is owned by b =Def c is an Information Content Entity (e.g., LinkedIn profile page) and b is the material entity that has ownership or control over c as information."
    )


class LinkedInCurrentJobPosition(RDFEntity):
    """
    LinkedIn current job position
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/CurrentJobPosition"
    )
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
    }
    _object_properties: ClassVar[set[str]] = {"concretizes", "inheres_in"}

    # Object properties
    concretizes: Optional[Union[str, ConnectionsExportFile, LinkedInProfilePage]] = (
        Field(
            description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
        )
    )
    inheres_in: Optional[Union[str, Person]] = Field(
        description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
    )


class LinkedInCurrentOrganization(RDFEntity):
    """
    LinkedIn current organization
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/CurrentOrganization"
    )
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
    }
    _object_properties: ClassVar[set[str]] = {"concretizes", "inheres_in"}

    # Object properties
    concretizes: Optional[Union[str, ConnectionsExportFile]] = Field(
        description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
    )
    inheres_in: Optional[Union[str, Person]] = Field(
        description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
    )


class LinkedInCurrentPublicURL(RDFEntity):
    """
    LinkedIn current public URL
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/CurrentPublicUrl"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
    }
    _object_properties: ClassVar[set[str]] = {"concretizes", "inheres_in"}

    # Object properties
    concretizes: Optional[Union[str, ConnectionsExportFile]] = Field(
        description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
    )
    inheres_in: Optional[Union[str, Person]] = Field(
        description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
    )


class LinkedInEmailAddress(RDFEntity):
    """
    LinkedIn email address
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/EmailAddress"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
    }
    _object_properties: ClassVar[set[str]] = {"concretizes", "inheres_in"}

    # Object properties
    concretizes: Optional[Union[str, ConnectionsExportFile]] = Field(
        description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
    )
    inheres_in: Optional[Union[str, Person]] = Field(
        description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
    )


class LinkedInConnectionRole(RDFEntity):
    """
    LinkedIn connection role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ConnectionRole"
    _property_uris: ClassVar[dict] = {
        "has_realization": "http://purl.obolibrary.org/obo/BFO_0000054",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
    }
    _object_properties: ClassVar[set[str]] = {"has_realization", "inheres_in"}

    # Object properties
    has_realization: Optional[Union[str, ActOfConnectionOnLinkedIn]] = Field(
        description="b has realization c =Def c realizes b"
    )
    inheres_in: Optional[Union[str, Person]] = Field(
        description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
    )


# Rebuild models to resolve forward references
ActOfConnectionOnLinkedIn.model_rebuild()
ISO8601UTCDateTime.model_rebuild()
Person.model_rebuild()
Organization.model_rebuild()
LinkedInLocation.model_rebuild()
LinkedInProfilePage.model_rebuild()
ConnectionsExportFile.model_rebuild()
LinkedInCurrentJobPosition.model_rebuild()
LinkedInCurrentOrganization.model_rebuild()
LinkedInCurrentPublicURL.model_rebuild()
LinkedInEmailAddress.model_rebuild()
LinkedInConnectionRole.model_rebuild()
