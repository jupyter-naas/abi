from __future__ import annotations
from typing import Annotated, Any, ClassVar, List, Optional, Union
from pydantic import BaseModel, Field
import uuid
import datetime
import os
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")


# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""

    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"
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

    def rdf(
        self, subject_uri: str | None = None, visited: set[str] | None = None
    ) -> Graph:
        """Generate RDF triples for this instance

        Args:
            subject_uri: Optional URI to use as subject (defaults to self._uri)
            visited: Set of URIs that have already been processed (for cycle detection)
        """
        # Initialize visited set if not provided
        if visited is None:
            visited = set()

        g = Graph()
        g.bind("cco", CCO)
        g.bind("bfo", BFO)
        g.bind("abi", ABI)
        g.bind("rdfs", RDFS)
        g.bind("rdf", RDF)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        # Use stored URI or provided subject_uri
        if subject_uri is None:
            subject_uri = self._uri
        subject = URIRef(subject_uri)

        # Check if we've already processed this entity (cycle detection)
        if subject_uri in visited:
            # Already processed, just return empty graph to avoid infinite recursion
            # The relationship triple will be added by the caller
            return g

        # Mark this entity as visited before processing
        visited.add(subject_uri)

        # Add class type
        if hasattr(self, "_class_uri"):
            g.add((subject, RDF.type, URIRef(self._class_uri)))

        # Add owl:NamedIndividual type
        g.add((subject, RDF.type, OWL.NamedIndividual))

        # Add label if it exists
        if hasattr(self, "label"):
            g.add((subject, RDFS.label, Literal(self.label)))

        object_props: set[str] = getattr(self, "_object_properties", set())

        # Add properties
        if hasattr(self, "_property_uris"):
            for prop_name, prop_uri in self._property_uris.items():
                is_object_prop = prop_name in object_props
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, "rdf") and hasattr(item, "_uri"):
                                # Check if this entity was already visited to prevent cycles
                                if item._uri not in visited:
                                    # Add triples from related object
                                    g += item.rdf(visited=visited)
                                # Always add the triple, even if already visited
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            elif is_object_prop and isinstance(item, (str, URIRef)):
                                g.add((subject, URIRef(prop_uri), URIRef(str(item))))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, "rdf") and hasattr(prop_value, "_uri"):
                        # Check if this entity was already visited to prevent cycles
                        if prop_value._uri not in visited:
                            # Add triples from related object
                            g += prop_value.rdf(visited=visited)
                        # Always add the triple, even if already visited
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
    _name: ClassVar[str] = "Act of connection on LinkedIn"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "connected_at": "http://ontology.naas.ai/abi/linkedin/connectedAt",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_associated_linkedin_quality": "http://ontology.naas.ai/abi/linkedin/hasAssociatedQuality",
        "involves_agent": "http://ontology.naas.ai/abi/linkedin/involvesAgent",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
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

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    concretizes: Optional[
        Annotated[
            List[Union[ConnectionsExportFile, LinkedInProfilePage, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    connected_at: Optional[
        Annotated[
            Union[ISO8601UTCDateTime, URIRef, str],
            Field(
                description="Relates an act of connection to the specific temporal entity at which that act of connection occurs or is realized."
            ),
        ]
    ] = "http://ontology.naas.ai/abi/unknown"
    has_associated_linkedin_quality: Optional[
        Annotated[
            List[
                Union[
                    LinkedInCurrentJobPosition,
                    LinkedInCurrentOrganization,
                    LinkedInCurrentPublicURL,
                    LinkedInEmailAddress,
                    URIRef,
                    str,
                ]
            ],
            Field(
                description="Relates a process (such as an act of connection) to a LinkedIn quality (such as CurrentJobPosition, CurrentOrganization, CurrentPublicUrl, or EmailAddress) that inheres in a participant of the process. This property is used to associate any LinkedIn quality with a process, emphasizing that the quality is relevant to or contextualizes the process, even if it is not a direct participant but is borne by one."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    involves_agent: Optional[
        Annotated[
            List[Union[Organization, Person, URIRef, str]],
            Field(
                description="Relates an event (such as an act of connection) to an agent (person or organization) involved in it. If an event involves agent x, then x is actively participating or is otherwise involved in the event."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    occurs_in: Optional[
        Annotated[
            List[Union[LinkedInLocation, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    realizes: Optional[
        Annotated[
            List[Union[LinkedInConnectionRole, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ISO8601UTCDateTime(RDFEntity):
    """
    ISO 8601 UTC DateTime
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/ISO8601UTCDateTime"
    _name: ClassVar[str] = "ISO 8601 UTC DateTime"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class Person(RDFEntity):
    """
    Person
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001262"
    _name: ClassVar[str] = "Person"
    _property_uris: ClassVar[dict] = {
        "agent_involved_in": "http://ontology.naas.ai/abi/linkedin/agentInvolvedIn",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_linkedin_connection_role": "http://ontology.naas.ai/abi/linkedin/hasConnectionRole",
        "has_linkedin_current_job_position": "http://ontology.naas.ai/abi/linkedin/hasCurrentJobPosition",
        "has_linkedin_current_organization": "http://ontology.naas.ai/abi/linkedin/hasCurrentOrganization",
        "has_linkedin_email_address": "http://ontology.naas.ai/abi/linkedin/hasEmailAddress",
        "has_linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/hasCurrentPublicUrl",
        "is_located_in": "http://ontology.naas.ai/abi/linkedin/locatedIn",
        "is_owner_of": "http://ontology.naas.ai/abi/linkedin/isOwnerOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
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

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    agent_involved_in: Optional[
        Annotated[
            List[Union[ActOfConnectionOnLinkedIn, URIRef, str]],
            Field(
                description="Relates an agent (person or organization) to an event in which the agent is involved or participates."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_linkedin_connection_role: Optional[
        Annotated[
            List[Union[LinkedInConnectionRole, URIRef, str]],
            Field(
                description="A person has LinkedIn connection role y if and only if y is a ConnectionRole (a quality) that inheres in the person and expresses their role in a connection as recorded on LinkedIn. This property connects a Person to the specific role they hold in a connection, as indicated on their LinkedIn profile."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_linkedin_current_job_position: Optional[
        Annotated[
            List[Union[LinkedInCurrentJobPosition, URIRef, str]],
            Field(
                description="A person has LinkedIn current job position y if and only if y is a CurrentJobPosition (a quality) that inheres in the person and expresses their present professional role or job title as recorded on LinkedIn. This property connects a Person to the specific professional position or title they currently hold, as indicated on their LinkedIn profile."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_linkedin_current_organization: Optional[
        Annotated[
            List[Union[LinkedInCurrentOrganization, URIRef, str]],
            Field(
                description="A person has LinkedIn current organization y if and only if y is a CurrentOrganization (a quality) that inheres in the person and expresses their present place of employment or affiliation as recorded on LinkedIn. This property connects a Person to the specific organization they currently work for or are affiliated with, as indicated on their LinkedIn profile."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_linkedin_email_address: Optional[
        Annotated[
            List[Union[LinkedInEmailAddress, URIRef, str]],
            Field(
                description="A person has LinkedIn email address y if and only if y is an EmailAddress (a quality) that inheres in the person and expresses their email address as recorded on LinkedIn. This property connects a Person to the specific email address they have registered on their LinkedIn profile."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    has_linkedin_public_url: Optional[
        Annotated[
            List[Union[LinkedInCurrentPublicURL, URIRef, str]],
            Field(
                description="A person has LinkedIn public URL y if and only if y is a CurrentPublicUrl (a quality) that inheres in the person and expresses their public web address as recorded on LinkedIn. This property connects a Person to the specific public web address they have registered on their LinkedIn profile."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_located_in: Optional[
        Annotated[
            List[Union[LinkedInLocation, URIRef, str]],
            Field(
                description="A person is located in y if and only if y is a UserSite that represents the location associated with the person on LinkedIn. This property connects a Person to the LinkedIn user site they are located in as indicated on their LinkedIn profile."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_owner_of: Optional[
        Annotated[
            List[Union[LinkedInProfilePage, URIRef, str]],
            Field(
                description="b is owner of c =Def b is a material entity (e.g., person or organization), c is an Information Content Entity (generically dependent continuant), and b has ownership or control over c as information."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class Organization(RDFEntity):
    """
    Organization
    """

    _class_uri: ClassVar[str] = "https://www.commoncoreontologies.org/ont00001180"
    _name: ClassVar[str] = "Organization"
    _property_uris: ClassVar[dict] = {
        "agent_involved_in": "http://ontology.naas.ai/abi/linkedin/agentInvolvedIn",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "holds_linkedin_quality": "http://ontology.naas.ai/abi/linkedin/holdsQuality",
        "is_located_in": "http://ontology.naas.ai/abi/linkedin/locatedIn",
        "is_owner_of": "http://ontology.naas.ai/abi/linkedin/isOwnerOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "agent_involved_in",
        "holds_linkedin_quality",
        "is_located_in",
        "is_owner_of",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    agent_involved_in: Optional[
        Annotated[
            List[Union[ActOfConnectionOnLinkedIn, URIRef, str]],
            Field(
                description="Relates an agent (person or organization) to an event in which the agent is involved or participates."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    holds_linkedin_quality: Optional[
        Annotated[
            List[Union[LinkedInCurrentOrganization, URIRef, str]],
            Field(
                description="A organization holds quality y if and only if y is a CurrentOrganization (a quality) that inheres in the organization and expresses a specific quality or characteristic as recorded on LinkedIn. This property connects a Organization to the specific quality or characteristic they hold that can be indicated on their LinkedIn organization page or on people's LinkedIn profile page who are part of the organization."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_located_in: Optional[
        Annotated[
            List[Union[LinkedInLocation, URIRef, str]],
            Field(
                description="A person is located in y if and only if y is a UserSite that represents the location associated with the person on LinkedIn. This property connects a Person to the LinkedIn user site they are located in as indicated on their LinkedIn profile."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_owner_of: Optional[
        Annotated[
            List[Union[ConnectionsExportFile, URIRef, str]],
            Field(
                description="b is owner of c =Def b is a material entity (e.g., person or organization), c is an Information Content Entity (generically dependent continuant), and b has ownership or control over c as information."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LinkedInLocation(RDFEntity):
    """
    LinkedIn Location
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Location"
    _name: ClassVar[str] = "LinkedIn Location"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")


class LinkedInProfilePage(RDFEntity):
    """
    A LinkedIn profile page must be registered in https://www.linkedin.com/in/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ProfilePage"
    _name: ClassVar[str] = "LinkedIn Profile Page"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_concretized_by": "http://purl.obolibrary.org/obo/BFO_0000058",
        "is_owned_by": "http://ontology.naas.ai/abi/linkedin/isOwnedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_concretized_by", "is_owned_by"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_concretized_by: Optional[
        Annotated[
            List[
                Union[
                    ActOfConnectionOnLinkedIn,
                    LinkedInConnectionRole,
                    LinkedInCurrentJobPosition,
                    LinkedInCurrentOrganization,
                    LinkedInCurrentPublicURL,
                    LinkedInEmailAddress,
                    URIRef,
                    str,
                ]
            ],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    is_owned_by: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="c is owned by b =Def c is an Information Content Entity (e.g., LinkedIn profile page) and b is the material entity that has ownership or control over c as information."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class ConnectionsExportFile(RDFEntity):
    """
    Connections export file
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/ConnectionsExportFile"
    )
    _name: ClassVar[str] = "Connections export file"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "is_owned_by": "http://ontology.naas.ai/abi/linkedin/isOwnedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"is_owned_by"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    is_owned_by: Optional[
        Annotated[
            List[Union[Organization, URIRef, str]],
            Field(
                description="c is owned by b =Def c is an Information Content Entity (e.g., LinkedIn profile page) and b is the material entity that has ownership or control over c as information."
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LinkedInCurrentJobPosition(RDFEntity):
    """
    LinkedIn current job position
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/CurrentJobPosition"
    )
    _name: ClassVar[str] = "LinkedIn current job position"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"concretizes", "inheres_in"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    concretizes: Optional[
        Annotated[
            List[Union[ConnectionsExportFile, LinkedInProfilePage, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    inheres_in: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LinkedInCurrentOrganization(RDFEntity):
    """
    LinkedIn current organization
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/CurrentOrganization"
    )
    _name: ClassVar[str] = "LinkedIn current organization"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"concretizes", "inheres_in"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    concretizes: Optional[
        Annotated[
            List[Union[ConnectionsExportFile, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    inheres_in: Optional[
        Annotated[
            List[Union[Organization, Person, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LinkedInCurrentPublicURL(RDFEntity):
    """
    LinkedIn current public URL
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/CurrentPublicUrl"
    _name: ClassVar[str] = "LinkedIn current public URL"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"concretizes", "inheres_in"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    concretizes: Optional[
        Annotated[
            List[Union[ConnectionsExportFile, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    inheres_in: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LinkedInEmailAddress(RDFEntity):
    """
    LinkedIn email address
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/EmailAddress"
    _name: ClassVar[str] = "LinkedIn email address"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://purl.obolibrary.org/obo/BFO_0000059",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"concretizes", "inheres_in"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    concretizes: Optional[
        Annotated[
            List[Union[ConnectionsExportFile, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    inheres_in: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


class LinkedInConnectionRole(RDFEntity):
    """
    LinkedIn connection role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ConnectionRole"
    _name: ClassVar[str] = "LinkedIn connection role"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://purl.obolibrary.org/obo/BFO_0000054",
        "inheres_in": "http://purl.obolibrary.org/obo/BFO_0000197",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {"has_realization", "inheres_in"}

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")]
    created: Annotated[
        Optional[datetime.datetime],
        Field(description="Date of creation of the resource."),
    ] = datetime.datetime.now()
    creator: Annotated[
        Optional[Any],
        Field(description="An entity responsible for making the resource."),
    ] = os.environ.get("USER")

    # Object properties
    has_realization: Optional[
        Annotated[
            List[Union[ActOfConnectionOnLinkedIn, URIRef, str]],
            Field(description="b has realization c =Def c realizes b"),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]
    inheres_in: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = ["http://ontology.naas.ai/abi/unknown"]


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
