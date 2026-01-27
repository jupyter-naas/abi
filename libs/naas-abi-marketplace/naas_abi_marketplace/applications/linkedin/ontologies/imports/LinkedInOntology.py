from __future__ import annotations
from typing import Any, ClassVar, Optional, Union
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


class SocialPage(RDFEntity):
    """
    A social page must be registered on a social media platform
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/SocialPage"
    _property_uris: ClassVar[dict] = {
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf"
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Object properties
    is_social_page_of: Optional[Any] = Field(
        description="Relates a social media page to the person or organization it represents."
    )


class LinkedInProperty(RDFEntity):
    """
    LinkedIn Property
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Property"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInIndustry(RDFEntity):
    """
    LinkedIn Industry
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Industry"
    _property_uris: ClassVar[dict] = {}
    _object_properties: ClassVar[set[str]] = set()

    pass


class LinkedInLocation(RDFEntity):
    """
    A LinkedIn Location represents a hierarchical geographical designation that can combine multiple location types (country, state/region, metropolitan area, city) into a single concatenated string.
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Location"
    _property_uris: ClassVar[dict] = {}
    _object_properties: ClassVar[set[str]] = set()

    pass


class ActOfLinkedInConnection(RDFEntity):
    """
    Act of LinkedIn Connection
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ActOfConnection"
    _property_uris: ClassVar[dict] = {}
    _object_properties: ClassVar[set[str]] = set()

    pass


class LinkedInPage(SocialPage, RDFEntity):
    """
    A LinkedIn page must be registered in https://www.linkedin.com/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Page"
    _property_uris: ClassVar[dict] = {
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Data properties
    description: Optional[str] = Field(description="The description of the entity.")
    entity_urn: Optional[str] = Field(description="The URN of the entity.")
    linkedin_id: Optional[str] = Field(description="The ID of the LinkedIn page.")
    linkedin_public_id: Optional[str] = Field(
        description="The public ID of the LinkedIn page. It might change over time."
    )
    linkedin_public_url: Optional[str] = Field(
        description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
    )
    linkedin_url: Optional[str] = Field(
        description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
    )
    localized_name: Optional[str] = Field(
        description="The localized name of the entity."
    )
    logo: Optional[str] = Field(description="The logo of the LinkedIn page.")

    # Object properties
    is_social_page_of: Optional[Any] = Field(
        description="Relates a social media page to the person or organization it represents."
    )


class LinkedInProfile(LinkedInProperty, RDFEntity):
    """
    LinkedIn Profile
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Profile"
    _property_uris: ClassVar[dict] = {
        "has_certification": "http://ontology.naas.ai/abi/linkedin/hasCertification",
        "has_course": "http://ontology.naas.ai/abi/linkedin/hasCourse",
        "has_education": "http://ontology.naas.ai/abi/linkedin/hasEducation",
        "has_honor": "http://ontology.naas.ai/abi/linkedin/hasHonor",
        "has_language": "http://ontology.naas.ai/abi/linkedin/hasLanguage",
        "has_organization": "http://ontology.naas.ai/abi/linkedin/hasOrganization",
        "has_patent": "http://ontology.naas.ai/abi/linkedin/hasPatent",
        "has_position": "http://ontology.naas.ai/abi/linkedin/hasPosition",
        "has_position_group": "http://ontology.naas.ai/abi/linkedin/hasPositionGroup",
        "has_project": "http://ontology.naas.ai/abi/linkedin/hasProject",
        "has_publication": "http://ontology.naas.ai/abi/linkedin/hasPublication",
        "has_skill": "http://ontology.naas.ai/abi/linkedin/hasSkill",
        "has_test_score": "http://ontology.naas.ai/abi/linkedin/hasTestScore",
        "has_volunteer_cause": "http://ontology.naas.ai/abi/linkedin/hasVolunteerCause",
        "has_volunteer_experience": "http://ontology.naas.ai/abi/linkedin/hasVolunteerExperience",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_profile_of": "http://ontology.naas.ai/abi/linkedin/isProfileOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_certification",
        "has_course",
        "has_education",
        "has_honor",
        "has_language",
        "has_organization",
        "has_patent",
        "has_position",
        "has_position_group",
        "has_project",
        "has_publication",
        "has_skill",
        "has_test_score",
        "has_volunteer_cause",
        "has_volunteer_experience",
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_profile_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    has_certification: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its certifications."
    )
    has_course: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its courses."
    )
    has_education: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its education history."
    )
    has_honor: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its honors."
    )
    has_language: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its languages."
    )
    has_organization: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its organizations."
    )
    has_patent: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its patents."
    )
    has_position: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its positions."
    )
    has_position_group: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its position groups."
    )
    has_project: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its projects."
    )
    has_publication: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its publications."
    )
    has_skill: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its skills."
    )
    has_test_score: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its test scores."
    )
    has_volunteer_cause: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its volunteer causes."
    )
    has_volunteer_experience: Optional[Union[str, LinkedInProperty]] = Field(
        description="Relates a LinkedIn profile to its volunteer experience."
    )
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_profile_of: Optional[Union[str, LinkedInProfilePage]] = Field(
        description="Relates a LinkedIn profile to the LinkedIn profile page it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInPatent(LinkedInProperty, RDFEntity):
    """
    LinkedIn Patent
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Patent"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInHonor(LinkedInProperty, RDFEntity):
    """
    LinkedIn Honor
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Honor"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInEducation(LinkedInProperty, RDFEntity):
    """
    LinkedIn Education
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Education"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInVolunteerExperience(LinkedInProperty, RDFEntity):
    """
    LinkedIn Volunteer Experience
    """

    _class_uri: ClassVar[str] = (
        "http://ontology.naas.ai/abi/linkedin/VolunteerExperience"
    )
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInVolunteerCause(LinkedInProperty, RDFEntity):
    """
    LinkedIn Volunteer Cause
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/VolunteerCause"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInTestScore(LinkedInProperty, RDFEntity):
    """
    LinkedIn Test Score
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/TestScore"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInSkill(LinkedInProperty, RDFEntity):
    """
    LinkedIn Skill
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Skill"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInProject(LinkedInProperty, RDFEntity):
    """
    LinkedIn Project
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Project"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInCertification(LinkedInProperty, RDFEntity):
    """
    LinkedIn Certification
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Certification"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInLanguage(LinkedInProperty, RDFEntity):
    """
    LinkedIn Language
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Language"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInCourse(LinkedInProperty, RDFEntity):
    """
    LinkedIn Course
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Course"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInPublication(LinkedInProperty, RDFEntity):
    """
    LinkedIn Publication
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Publication"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInPositionGroup(LinkedInProperty, RDFEntity):
    """
    LinkedIn Position Group
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/PositionGroup"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInOrganization(LinkedInProperty, RDFEntity):
    """
    LinkedIn Organization
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Organization"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInPosition(LinkedInProperty, RDFEntity):
    """
    LinkedIn Position
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/Position"
    _property_uris: ClassVar[dict] = {
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInFollowingInfo(LinkedInProperty, RDFEntity):
    """
    LinkedIn Following Info
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/FollowingInfo"
    _property_uris: ClassVar[dict] = {
        "follower_count": "http://ontology.naas.ai/abi/linkedin/followerCount",
        "is_certification_of": "http://ontology.naas.ai/abi/linkedin/isCertificationOf",
        "is_course_of": "http://ontology.naas.ai/abi/linkedin/isCourseOf",
        "is_education_of": "http://ontology.naas.ai/abi/linkedin/isEducationOf",
        "is_honor_of": "http://ontology.naas.ai/abi/linkedin/isHonorOf",
        "is_language_of": "http://ontology.naas.ai/abi/linkedin/isLanguageOf",
        "is_organization_of": "http://ontology.naas.ai/abi/linkedin/isOrganizationOf",
        "is_patent_of": "http://ontology.naas.ai/abi/linkedin/isPatentOf",
        "is_position_group_of": "http://ontology.naas.ai/abi/linkedin/isPositionGroupOf",
        "is_position_of": "http://ontology.naas.ai/abi/linkedin/isPositionOf",
        "is_project_of": "http://ontology.naas.ai/abi/linkedin/isProjectOf",
        "is_publication_of": "http://ontology.naas.ai/abi/linkedin/isPublicationOf",
        "is_skill_of": "http://ontology.naas.ai/abi/linkedin/isSkillOf",
        "is_test_score_of": "http://ontology.naas.ai/abi/linkedin/isTestScoreOf",
        "is_volunteer_cause_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf",
        "is_volunteer_experience_of": "http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf",
    }
    _object_properties: ClassVar[set[str]] = {
        "is_certification_of",
        "is_course_of",
        "is_education_of",
        "is_honor_of",
        "is_language_of",
        "is_organization_of",
        "is_patent_of",
        "is_position_group_of",
        "is_position_of",
        "is_project_of",
        "is_publication_of",
        "is_skill_of",
        "is_test_score_of",
        "is_volunteer_cause_of",
        "is_volunteer_experience_of",
    }

    # Data properties
    follower_count: Optional[Any] = Field(
        description="The number of followers for a LinkedIn entity."
    )

    # Object properties
    is_certification_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a certification to the LinkedIn profile it belongs to."
    )
    is_course_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a course to the LinkedIn profile it belongs to."
    )
    is_education_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an education entry to the LinkedIn profile it belongs to."
    )
    is_honor_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an honor to the LinkedIn profile it belongs to."
    )
    is_language_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a language to the LinkedIn profile it belongs to."
    )
    is_organization_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates an organization to the LinkedIn profile it belongs to."
    )
    is_patent_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a patent to the LinkedIn profile it belongs to."
    )
    is_position_group_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position group to the LinkedIn profile it belongs to."
    )
    is_position_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a position to the LinkedIn profile it belongs to."
    )
    is_project_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a project to the LinkedIn profile it belongs to."
    )
    is_publication_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a publication to the LinkedIn profile it belongs to."
    )
    is_skill_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a skill to the LinkedIn profile it belongs to."
    )
    is_test_score_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a test score to the LinkedIn profile it belongs to."
    )
    is_volunteer_cause_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer cause to the LinkedIn profile it belongs to."
    )
    is_volunteer_experience_of: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a volunteer experience to the LinkedIn profile it belongs to."
    )


class LinkedInProfilePage(LinkedInPage, RDFEntity):
    """
    A LinkedIn profile page must be registered in https://www.linkedin.com/in/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/ProfilePage"
    _property_uris: ClassVar[dict] = {
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "has_profile": "http://ontology.naas.ai/abi/linkedin/hasProfile",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"has_profile", "is_social_page_of"}

    # Data properties
    description: Optional[str] = Field(description="The description of the entity.")
    entity_urn: Optional[str] = Field(description="The URN of the entity.")
    linkedin_id: Optional[str] = Field(description="The ID of the LinkedIn page.")
    linkedin_public_id: Optional[str] = Field(
        description="The public ID of the LinkedIn page. It might change over time."
    )
    linkedin_public_url: Optional[str] = Field(
        description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
    )
    linkedin_url: Optional[str] = Field(
        description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
    )
    localized_name: Optional[str] = Field(
        description="The localized name of the entity."
    )
    logo: Optional[str] = Field(description="The logo of the LinkedIn page.")

    # Object properties
    has_profile: Optional[Union[str, LinkedInProfile]] = Field(
        description="Relates a LinkedIn profile page to its profile."
    )
    is_social_page_of: Optional[Any] = Field(
        description="Relates a social media page to the person or organization it represents."
    )


class LinkedInCompanyPage(LinkedInPage, RDFEntity):
    """
    A LinkedIn company page must be registered in https://www.linkedin.com/company/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/CompanyPage"
    _property_uris: ClassVar[dict] = {
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Data properties
    description: Optional[str] = Field(description="The description of the entity.")
    entity_urn: Optional[str] = Field(description="The URN of the entity.")
    linkedin_id: Optional[str] = Field(description="The ID of the LinkedIn page.")
    linkedin_public_id: Optional[str] = Field(
        description="The public ID of the LinkedIn page. It might change over time."
    )
    linkedin_public_url: Optional[str] = Field(
        description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
    )
    linkedin_url: Optional[str] = Field(
        description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
    )
    localized_name: Optional[str] = Field(
        description="The localized name of the entity."
    )
    logo: Optional[str] = Field(description="The logo of the LinkedIn page.")

    # Object properties
    is_social_page_of: Optional[Any] = Field(
        description="Relates a social media page to the person or organization it represents."
    )


class LinkedInSchoolPage(LinkedInPage, RDFEntity):
    """
    A LinkedIn school page must be registered in https://www.linkedin.com/school/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/SchoolPage"
    _property_uris: ClassVar[dict] = {
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Data properties
    description: Optional[str] = Field(description="The description of the entity.")
    entity_urn: Optional[str] = Field(description="The URN of the entity.")
    linkedin_id: Optional[str] = Field(description="The ID of the LinkedIn page.")
    linkedin_public_id: Optional[str] = Field(
        description="The public ID of the LinkedIn page. It might change over time."
    )
    linkedin_public_url: Optional[str] = Field(
        description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
    )
    linkedin_url: Optional[str] = Field(
        description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
    )
    localized_name: Optional[str] = Field(
        description="The localized name of the entity."
    )
    logo: Optional[str] = Field(description="The logo of the LinkedIn page.")

    # Object properties
    is_social_page_of: Optional[Any] = Field(
        description="Relates a social media page to the person or organization it represents."
    )


class LinkedInJobSearchPage(LinkedInPage, RDFEntity):
    """
    A LinkedIn job search page must be registered in https://www.linkedin.com/jobs/
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/abi/linkedin/JobSearchPage"
    _property_uris: ClassVar[dict] = {
        "description": "http://ontology.naas.ai/abi/linkedin/description",
        "entity_urn": "http://ontology.naas.ai/abi/linkedin/entityUrn",
        "is_social_page_of": "http://ontology.naas.ai/abi/linkedin/isSocialPageOf",
        "linkedin_id": "http://ontology.naas.ai/abi/linkedin/id",
        "linkedin_public_id": "http://ontology.naas.ai/abi/linkedin/public_id",
        "linkedin_public_url": "http://ontology.naas.ai/abi/linkedin/public_url",
        "linkedin_url": "http://ontology.naas.ai/abi/linkedin/url",
        "localized_name": "http://ontology.naas.ai/abi/linkedin/localizedName",
        "logo": "http://ontology.naas.ai/abi/linkedin/logo",
    }
    _object_properties: ClassVar[set[str]] = {"is_social_page_of"}

    # Data properties
    description: Optional[str] = Field(description="The description of the entity.")
    entity_urn: Optional[str] = Field(description="The URN of the entity.")
    linkedin_id: Optional[str] = Field(description="The ID of the LinkedIn page.")
    linkedin_public_id: Optional[str] = Field(
        description="The public ID of the LinkedIn page. It might change over time."
    )
    linkedin_public_url: Optional[str] = Field(
        description="The public URL of the LinkedIn page. It uses the LinkedIn Public ID as identifier."
    )
    linkedin_url: Optional[str] = Field(
        description="The URL of the LinkedIn page. It uses the LinkedIn ID as a unique identifier."
    )
    localized_name: Optional[str] = Field(
        description="The localized name of the entity."
    )
    logo: Optional[str] = Field(description="The logo of the LinkedIn page.")

    # Object properties
    is_social_page_of: Optional[Any] = Field(
        description="Relates a social media page to the person or organization it represents."
    )


# Rebuild models to resolve forward references
SocialPage.model_rebuild()
LinkedInProperty.model_rebuild()
LinkedInIndustry.model_rebuild()
LinkedInLocation.model_rebuild()
ActOfLinkedInConnection.model_rebuild()
LinkedInPage.model_rebuild()
LinkedInProfile.model_rebuild()
LinkedInPatent.model_rebuild()
LinkedInHonor.model_rebuild()
LinkedInEducation.model_rebuild()
LinkedInVolunteerExperience.model_rebuild()
LinkedInVolunteerCause.model_rebuild()
LinkedInTestScore.model_rebuild()
LinkedInSkill.model_rebuild()
LinkedInProject.model_rebuild()
LinkedInCertification.model_rebuild()
LinkedInLanguage.model_rebuild()
LinkedInCourse.model_rebuild()
LinkedInPublication.model_rebuild()
LinkedInPositionGroup.model_rebuild()
LinkedInOrganization.model_rebuild()
LinkedInPosition.model_rebuild()
LinkedInFollowingInfo.model_rebuild()
LinkedInProfilePage.model_rebuild()
LinkedInCompanyPage.model_rebuild()
LinkedInSchoolPage.model_rebuild()
LinkedInJobSearchPage.model_rebuild()
