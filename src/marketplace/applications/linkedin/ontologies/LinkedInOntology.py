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


class SocialPage(RDFEntity):
    """
    A social page must be registered on a social media platform
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/SocialPage'
    _property_uris: ClassVar[dict] = {'isSocialPageOf': 'http://ontology.naas.ai/abi/linkedin/isSocialPageOf'}

    # Object properties
    isSocialPageOf: Optional[N4258112b8430493caea35316b03ef5acb4] = Field(default=None)

class Property(RDFEntity):
    """
    LinkedIn Property
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Property'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Industry(RDFEntity):
    """
    LinkedIn Industry
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Industry'
    _property_uris: ClassVar[dict] = {}
    pass

class N4258112b8430493caea35316b03ef5acb1(RDFEntity):
    _class_uri: ClassVar[str] = 'n4258112b8430493caea35316b03ef5acb1'
    _property_uris: ClassVar[dict] = {'hasSocialPage': 'http://ontology.naas.ai/abi/linkedin/hasSocialPage'}

    # Object properties
    hasSocialPage: Optional[SocialPage] = Field(default=None)

class N4258112b8430493caea35316b03ef5acb4(RDFEntity):
    _class_uri: ClassVar[str] = 'n4258112b8430493caea35316b03ef5acb4'
    _property_uris: ClassVar[dict] = {}
    pass

class Page(SocialPage, RDFEntity):
    """
    A LinkedIn page must be registered in https://www.linkedin.com/
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Page'
    _property_uris: ClassVar[dict] = {'description': 'http://ontology.naas.ai/abi/linkedin/description', 'entityUrn': 'http://ontology.naas.ai/abi/linkedin/entityUrn', 'id': 'http://ontology.naas.ai/abi/linkedin/id', 'isSocialPageOf': 'http://ontology.naas.ai/abi/linkedin/isSocialPageOf', 'localizedName': 'http://ontology.naas.ai/abi/linkedin/localizedName', 'logo': 'http://ontology.naas.ai/abi/linkedin/logo', 'public_id': 'http://ontology.naas.ai/abi/linkedin/public_id', 'public_url': 'http://ontology.naas.ai/abi/linkedin/public_url', 'url': 'http://ontology.naas.ai/abi/linkedin/url'}

    # Data properties
    description: Optional[str] = Field(default=None)
    entityUrn: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    localizedName: Optional[str] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    public_id: Optional[str] = Field(default=None)
    public_url: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    isSocialPageOf: Optional[N4258112b8430493caea35316b03ef5acb4] = Field(default=None)

class Profile(Property, RDFEntity):
    """
    LinkedIn Profile
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Profile'
    _property_uris: ClassVar[dict] = {'hasCertification': 'http://ontology.naas.ai/abi/linkedin/hasCertification', 'hasCourse': 'http://ontology.naas.ai/abi/linkedin/hasCourse', 'hasEducation': 'http://ontology.naas.ai/abi/linkedin/hasEducation', 'hasHonor': 'http://ontology.naas.ai/abi/linkedin/hasHonor', 'hasLanguage': 'http://ontology.naas.ai/abi/linkedin/hasLanguage', 'hasOrganization': 'http://ontology.naas.ai/abi/linkedin/hasOrganization', 'hasPatent': 'http://ontology.naas.ai/abi/linkedin/hasPatent', 'hasPosition': 'http://ontology.naas.ai/abi/linkedin/hasPosition', 'hasPositionGroup': 'http://ontology.naas.ai/abi/linkedin/hasPositionGroup', 'hasProject': 'http://ontology.naas.ai/abi/linkedin/hasProject', 'hasPublication': 'http://ontology.naas.ai/abi/linkedin/hasPublication', 'hasSkill': 'http://ontology.naas.ai/abi/linkedin/hasSkill', 'hasTestScore': 'http://ontology.naas.ai/abi/linkedin/hasTestScore', 'hasVolunteerCause': 'http://ontology.naas.ai/abi/linkedin/hasVolunteerCause', 'hasVolunteerExperience': 'http://ontology.naas.ai/abi/linkedin/hasVolunteerExperience', 'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProfileOf': 'http://ontology.naas.ai/abi/linkedin/isProfileOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    hasCertification: Optional[Property] = Field(default=None)
    hasCourse: Optional[Property] = Field(default=None)
    hasEducation: Optional[Property] = Field(default=None)
    hasHonor: Optional[Property] = Field(default=None)
    hasLanguage: Optional[Property] = Field(default=None)
    hasOrganization: Optional[Property] = Field(default=None)
    hasPatent: Optional[Property] = Field(default=None)
    hasPosition: Optional[Property] = Field(default=None)
    hasPositionGroup: Optional[Property] = Field(default=None)
    hasProject: Optional[Property] = Field(default=None)
    hasPublication: Optional[Property] = Field(default=None)
    hasSkill: Optional[Property] = Field(default=None)
    hasTestScore: Optional[Property] = Field(default=None)
    hasVolunteerCause: Optional[Property] = Field(default=None)
    hasVolunteerExperience: Optional[Property] = Field(default=None)
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProfileOf: Optional[ProfilePage] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Patent(Property, RDFEntity):
    """
    LinkedIn Patent
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Patent'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Honor(Property, RDFEntity):
    """
    LinkedIn Honor
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Honor'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Education(Property, RDFEntity):
    """
    LinkedIn Education
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Education'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class VolunteerExperience(Property, RDFEntity):
    """
    LinkedIn Volunteer Experience
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/VolunteerExperience'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class VolunteerCause(Property, RDFEntity):
    """
    LinkedIn Volunteer Cause
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/VolunteerCause'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class TestScore(Property, RDFEntity):
    """
    LinkedIn Test Score
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/TestScore'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Skill(Property, RDFEntity):
    """
    LinkedIn Skill
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Skill'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Project(Property, RDFEntity):
    """
    LinkedIn Project
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Project'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Certification(Property, RDFEntity):
    """
    LinkedIn Certification
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Certification'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Language(Property, RDFEntity):
    """
    LinkedIn Language
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Language'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Course(Property, RDFEntity):
    """
    LinkedIn Course
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Course'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Publication(Property, RDFEntity):
    """
    LinkedIn Publication
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Publication'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class PositionGroup(Property, RDFEntity):
    """
    LinkedIn Position Group
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/PositionGroup'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Organization(Property, RDFEntity):
    """
    LinkedIn Organization
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Organization'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class Position(Property, RDFEntity):
    """
    LinkedIn Position
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/Position'
    _property_uris: ClassVar[dict] = {'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class FollowingInfo(Property, RDFEntity):
    """
    LinkedIn Following Info
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/FollowingInfo'
    _property_uris: ClassVar[dict] = {'followerCount': 'http://ontology.naas.ai/abi/linkedin/followerCount', 'isCertificationOf': 'http://ontology.naas.ai/abi/linkedin/isCertificationOf', 'isCourseOf': 'http://ontology.naas.ai/abi/linkedin/isCourseOf', 'isEducationOf': 'http://ontology.naas.ai/abi/linkedin/isEducationOf', 'isHonorOf': 'http://ontology.naas.ai/abi/linkedin/isHonorOf', 'isLanguageOf': 'http://ontology.naas.ai/abi/linkedin/isLanguageOf', 'isOrganizationOf': 'http://ontology.naas.ai/abi/linkedin/isOrganizationOf', 'isPatentOf': 'http://ontology.naas.ai/abi/linkedin/isPatentOf', 'isPositionGroupOf': 'http://ontology.naas.ai/abi/linkedin/isPositionGroupOf', 'isPositionOf': 'http://ontology.naas.ai/abi/linkedin/isPositionOf', 'isProjectOf': 'http://ontology.naas.ai/abi/linkedin/isProjectOf', 'isPublicationOf': 'http://ontology.naas.ai/abi/linkedin/isPublicationOf', 'isSkillOf': 'http://ontology.naas.ai/abi/linkedin/isSkillOf', 'isTestScoreOf': 'http://ontology.naas.ai/abi/linkedin/isTestScoreOf', 'isVolunteerCauseOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerCauseOf', 'isVolunteerExperienceOf': 'http://ontology.naas.ai/abi/linkedin/isVolunteerExperienceOf'}

    # Data properties
    followerCount: Optional[Any] = Field(default=None)

    # Object properties
    isCertificationOf: Optional[Profile] = Field(default=None)
    isCourseOf: Optional[Profile] = Field(default=None)
    isEducationOf: Optional[Profile] = Field(default=None)
    isHonorOf: Optional[Profile] = Field(default=None)
    isLanguageOf: Optional[Profile] = Field(default=None)
    isOrganizationOf: Optional[Profile] = Field(default=None)
    isPatentOf: Optional[Profile] = Field(default=None)
    isPositionGroupOf: Optional[Profile] = Field(default=None)
    isPositionOf: Optional[Profile] = Field(default=None)
    isProjectOf: Optional[Profile] = Field(default=None)
    isPublicationOf: Optional[Profile] = Field(default=None)
    isSkillOf: Optional[Profile] = Field(default=None)
    isTestScoreOf: Optional[Profile] = Field(default=None)
    isVolunteerCauseOf: Optional[Profile] = Field(default=None)
    isVolunteerExperienceOf: Optional[Profile] = Field(default=None)

class ProfilePage(Page, RDFEntity):
    """
    A LinkedIn profile page must be registered in https://www.linkedin.com/in/
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/ProfilePage'
    _property_uris: ClassVar[dict] = {'description': 'http://ontology.naas.ai/abi/linkedin/description', 'entityUrn': 'http://ontology.naas.ai/abi/linkedin/entityUrn', 'hasProfile': 'http://ontology.naas.ai/abi/linkedin/hasProfile', 'id': 'http://ontology.naas.ai/abi/linkedin/id', 'isSocialPageOf': 'http://ontology.naas.ai/abi/linkedin/isSocialPageOf', 'localizedName': 'http://ontology.naas.ai/abi/linkedin/localizedName', 'logo': 'http://ontology.naas.ai/abi/linkedin/logo', 'public_id': 'http://ontology.naas.ai/abi/linkedin/public_id', 'public_url': 'http://ontology.naas.ai/abi/linkedin/public_url', 'url': 'http://ontology.naas.ai/abi/linkedin/url'}

    # Data properties
    description: Optional[str] = Field(default=None)
    entityUrn: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    localizedName: Optional[str] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    public_id: Optional[str] = Field(default=None)
    public_url: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    hasProfile: Optional[Profile] = Field(default=None)
    isSocialPageOf: Optional[N4258112b8430493caea35316b03ef5acb4] = Field(default=None)

class CompanyPage(Page, RDFEntity):
    """
    A LinkedIn company page must be registered in https://www.linkedin.com/company/
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/CompanyPage'
    _property_uris: ClassVar[dict] = {'description': 'http://ontology.naas.ai/abi/linkedin/description', 'entityUrn': 'http://ontology.naas.ai/abi/linkedin/entityUrn', 'id': 'http://ontology.naas.ai/abi/linkedin/id', 'isSocialPageOf': 'http://ontology.naas.ai/abi/linkedin/isSocialPageOf', 'localizedName': 'http://ontology.naas.ai/abi/linkedin/localizedName', 'logo': 'http://ontology.naas.ai/abi/linkedin/logo', 'public_id': 'http://ontology.naas.ai/abi/linkedin/public_id', 'public_url': 'http://ontology.naas.ai/abi/linkedin/public_url', 'url': 'http://ontology.naas.ai/abi/linkedin/url'}

    # Data properties
    description: Optional[str] = Field(default=None)
    entityUrn: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    localizedName: Optional[str] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    public_id: Optional[str] = Field(default=None)
    public_url: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    isSocialPageOf: Optional[N4258112b8430493caea35316b03ef5acb4] = Field(default=None)

class SchoolPage(Page, RDFEntity):
    """
    A LinkedIn school page must be registered in https://www.linkedin.com/school/
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/SchoolPage'
    _property_uris: ClassVar[dict] = {'description': 'http://ontology.naas.ai/abi/linkedin/description', 'entityUrn': 'http://ontology.naas.ai/abi/linkedin/entityUrn', 'id': 'http://ontology.naas.ai/abi/linkedin/id', 'isSocialPageOf': 'http://ontology.naas.ai/abi/linkedin/isSocialPageOf', 'localizedName': 'http://ontology.naas.ai/abi/linkedin/localizedName', 'logo': 'http://ontology.naas.ai/abi/linkedin/logo', 'public_id': 'http://ontology.naas.ai/abi/linkedin/public_id', 'public_url': 'http://ontology.naas.ai/abi/linkedin/public_url', 'url': 'http://ontology.naas.ai/abi/linkedin/url'}

    # Data properties
    description: Optional[str] = Field(default=None)
    entityUrn: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    localizedName: Optional[str] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    public_id: Optional[str] = Field(default=None)
    public_url: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    isSocialPageOf: Optional[N4258112b8430493caea35316b03ef5acb4] = Field(default=None)

class JobSearchPage(Page, RDFEntity):
    """
    A LinkedIn job search page must be registered in https://www.linkedin.com/jobs/
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/linkedin/JobSearchPage'
    _property_uris: ClassVar[dict] = {'description': 'http://ontology.naas.ai/abi/linkedin/description', 'entityUrn': 'http://ontology.naas.ai/abi/linkedin/entityUrn', 'id': 'http://ontology.naas.ai/abi/linkedin/id', 'isSocialPageOf': 'http://ontology.naas.ai/abi/linkedin/isSocialPageOf', 'localizedName': 'http://ontology.naas.ai/abi/linkedin/localizedName', 'logo': 'http://ontology.naas.ai/abi/linkedin/logo', 'public_id': 'http://ontology.naas.ai/abi/linkedin/public_id', 'public_url': 'http://ontology.naas.ai/abi/linkedin/public_url', 'url': 'http://ontology.naas.ai/abi/linkedin/url'}

    # Data properties
    description: Optional[str] = Field(default=None)
    entityUrn: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    localizedName: Optional[str] = Field(default=None)
    logo: Optional[str] = Field(default=None)
    public_id: Optional[str] = Field(default=None)
    public_url: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    isSocialPageOf: Optional[N4258112b8430493caea35316b03ef5acb4] = Field(default=None)

# Rebuild models to resolve forward references
SocialPage.model_rebuild()
Property.model_rebuild()
Industry.model_rebuild()
N4258112b8430493caea35316b03ef5acb1.model_rebuild()
N4258112b8430493caea35316b03ef5acb4.model_rebuild()
Page.model_rebuild()
Profile.model_rebuild()
Patent.model_rebuild()
Honor.model_rebuild()
Education.model_rebuild()
VolunteerExperience.model_rebuild()
VolunteerCause.model_rebuild()
TestScore.model_rebuild()
Skill.model_rebuild()
Project.model_rebuild()
Certification.model_rebuild()
Language.model_rebuild()
Course.model_rebuild()
Publication.model_rebuild()
PositionGroup.model_rebuild()
Organization.model_rebuild()
Position.model_rebuild()
FollowingInfo.model_rebuild()
ProfilePage.model_rebuild()
CompanyPage.model_rebuild()
SchoolPage.model_rebuild()
JobSearchPage.model_rebuild()
