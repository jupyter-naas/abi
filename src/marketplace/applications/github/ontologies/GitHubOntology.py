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


class GitHubPage(RDFEntity):
    """
    A GitHub page must be registered in https://github.com/
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/GitHubPage'
    _property_uris: ClassVar[dict] = {'id': 'http://ontology.naas.ai/abi/github/id', 'isGitHubPageOf': 'http://ontology.naas.ai/abi/github/isGitHubPageOf', 'url': 'http://ontology.naas.ai/abi/github/url'}

    # Data properties
    id: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    isGitHubPageOf: Optional[N7766f0aed17c489fa12dcb75722e24c2b4] = Field(default=None)

class Property(RDFEntity):
    """
    GitHub Property
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/Property'
    _property_uris: ClassVar[dict] = {}
    pass

class N7766f0aed17c489fa12dcb75722e24c2b1(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b1'
    _property_uris: ClassVar[dict] = {'hasGitHubPage': 'http://ontology.naas.ai/abi/github/hasGitHubPage'}

    # Object properties
    hasGitHubPage: Optional[GitHubPage] = Field(default=None)

class N7766f0aed17c489fa12dcb75722e24c2b4(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b4'
    _property_uris: ClassVar[dict] = {}
    pass

class N7766f0aed17c489fa12dcb75722e24c2b7(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b7'
    _property_uris: ClassVar[dict] = {'hasRepository': 'http://ontology.naas.ai/abi/github/hasRepository'}

    # Object properties
    hasRepository: Optional[Repository] = Field(default=None)

class N7766f0aed17c489fa12dcb75722e24c2b10(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b10'
    _property_uris: ClassVar[dict] = {}
    pass

class N7766f0aed17c489fa12dcb75722e24c2b13(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b13'
    _property_uris: ClassVar[dict] = {'name': 'http://ontology.naas.ai/abi/github/name'}

    # Data properties
    name: Optional[str] = Field(default=None)

class N7766f0aed17c489fa12dcb75722e24c2b17(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b17'
    _property_uris: ClassVar[dict] = {'title': 'http://ontology.naas.ai/abi/github/title'}

    # Data properties
    title: Optional[str] = Field(default=None)

class N7766f0aed17c489fa12dcb75722e24c2b20(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b20'
    _property_uris: ClassVar[dict] = {'body': 'http://ontology.naas.ai/abi/github/body'}

    # Data properties
    body: Optional[str] = Field(default=None)

class N7766f0aed17c489fa12dcb75722e24c2b24(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b24'
    _property_uris: ClassVar[dict] = {'state': 'http://ontology.naas.ai/abi/github/state'}

    # Data properties
    state: Optional[str] = Field(default=None)

class N7766f0aed17c489fa12dcb75722e24c2b27(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b27'
    _property_uris: ClassVar[dict] = {'number': 'http://ontology.naas.ai/abi/github/number'}

    # Data properties
    number: Optional[Any] = Field(default=None)

class N7766f0aed17c489fa12dcb75722e24c2b30(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b30'
    _property_uris: ClassVar[dict] = {'createdAt': 'http://ontology.naas.ai/abi/github/createdAt'}

    # Data properties
    createdAt: Optional[datetime.datetime] = Field(default=None)

class N7766f0aed17c489fa12dcb75722e24c2b38(RDFEntity):
    _class_uri: ClassVar[str] = 'n7766f0aed17c489fa12dcb75722e24c2b38'
    _property_uris: ClassVar[dict] = {'updatedAt': 'http://ontology.naas.ai/abi/github/updatedAt'}

    # Data properties
    updatedAt: Optional[datetime.datetime] = Field(default=None)

class UserPage(GitHubPage, RDFEntity):
    """
    A GitHub user page must be registered in https://github.com/username
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/UserPage'
    _property_uris: ClassVar[dict] = {'hasUser': 'http://ontology.naas.ai/abi/github/hasUser', 'id': 'http://ontology.naas.ai/abi/github/id', 'isGitHubPageOf': 'http://ontology.naas.ai/abi/github/isGitHubPageOf', 'url': 'http://ontology.naas.ai/abi/github/url'}

    # Data properties
    id: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    hasUser: Optional[User] = Field(default=None)
    isGitHubPageOf: Optional[N7766f0aed17c489fa12dcb75722e24c2b4] = Field(default=None)

class OrganizationPage(GitHubPage, RDFEntity):
    """
    A GitHub organization page must be registered in https://github.com/organization
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/OrganizationPage'
    _property_uris: ClassVar[dict] = {'hasOrganization': 'http://ontology.naas.ai/abi/github/hasOrganization', 'id': 'http://ontology.naas.ai/abi/github/id', 'isGitHubPageOf': 'http://ontology.naas.ai/abi/github/isGitHubPageOf', 'url': 'http://ontology.naas.ai/abi/github/url'}

    # Data properties
    id: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    hasOrganization: Optional[Organization] = Field(default=None)
    isGitHubPageOf: Optional[N7766f0aed17c489fa12dcb75722e24c2b4] = Field(default=None)

class RepositoryPage(GitHubPage, RDFEntity):
    """
    A GitHub repository page must be registered in https://github.com/owner/repository
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/RepositoryPage'
    _property_uris: ClassVar[dict] = {'id': 'http://ontology.naas.ai/abi/github/id', 'isGitHubPageOf': 'http://ontology.naas.ai/abi/github/isGitHubPageOf', 'url': 'http://ontology.naas.ai/abi/github/url'}

    # Data properties
    id: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)

    # Object properties
    isGitHubPageOf: Optional[N7766f0aed17c489fa12dcb75722e24c2b4] = Field(default=None)

class User(Property, RDFEntity):
    """
    GitHub User
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/User'
    _property_uris: ClassVar[dict] = {'bio': 'http://ontology.naas.ai/abi/github/bio', 'blog': 'http://ontology.naas.ai/abi/github/blog', 'company': 'http://ontology.naas.ai/abi/github/company', 'email': 'http://ontology.naas.ai/abi/github/email', 'followers': 'http://ontology.naas.ai/abi/github/followers', 'following': 'http://ontology.naas.ai/abi/github/following', 'isUserOf': 'http://ontology.naas.ai/abi/github/isUserOf', 'location': 'http://ontology.naas.ai/abi/github/location', 'login': 'http://ontology.naas.ai/abi/github/login', 'publicRepos': 'http://ontology.naas.ai/abi/github/publicRepos'}

    # Data properties
    bio: Optional[str] = Field(default=None)
    blog: Optional[str] = Field(default=None)
    company: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    followers: Optional[Any] = Field(default=None)
    following: Optional[Any] = Field(default=None)
    location: Optional[str] = Field(default=None)
    login: Optional[str] = Field(default=None)
    publicRepos: Optional[Any] = Field(default=None)

    # Object properties
    isUserOf: Optional[UserPage] = Field(default=None)

class Repository(Property, RDFEntity):
    """
    GitHub Repository
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/Repository'
    _property_uris: ClassVar[dict] = {'description': 'http://ontology.naas.ai/abi/github/description', 'forks': 'http://ontology.naas.ai/abi/github/forks', 'hasActivity': 'http://ontology.naas.ai/abi/github/hasActivity', 'hasContributor': 'http://ontology.naas.ai/abi/github/hasContributor', 'hasIssue': 'http://ontology.naas.ai/abi/github/hasIssue', 'hasPullRequest': 'http://ontology.naas.ai/abi/github/hasPullRequest', 'hasSecret': 'http://ontology.naas.ai/abi/github/hasSecret', 'isRepositoryOf': 'http://ontology.naas.ai/abi/github/isRepositoryOf', 'language': 'http://ontology.naas.ai/abi/github/language', 'private': 'http://ontology.naas.ai/abi/github/private', 'stars': 'http://ontology.naas.ai/abi/github/stars'}

    # Data properties
    description: Optional[str] = Field(default=None)
    forks: Optional[Any] = Field(default=None)
    language: Optional[str] = Field(default=None)
    private: Optional[bool] = Field(default=None)
    stars: Optional[Any] = Field(default=None)

    # Object properties
    hasActivity: Optional[RepositoryActivity] = Field(default=None)
    hasContributor: Optional[Contributor] = Field(default=None)
    hasIssue: Optional[Issue] = Field(default=None)
    hasPullRequest: Optional[PullRequest] = Field(default=None)
    hasSecret: Optional[Secret] = Field(default=None)
    isRepositoryOf: Optional[N7766f0aed17c489fa12dcb75722e24c2b10] = Field(default=None)

class Issue(Property, RDFEntity):
    """
    GitHub Issue
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/Issue'
    _property_uris: ClassVar[dict] = {'hasAssignee': 'http://ontology.naas.ai/abi/github/hasAssignee', 'hasIssueComment': 'http://ontology.naas.ai/abi/github/hasIssueComment', 'isIssueOf': 'http://ontology.naas.ai/abi/github/isIssueOf', 'labels': 'http://ontology.naas.ai/abi/github/labels'}

    # Data properties
    labels: Optional[str] = Field(default=None)

    # Object properties
    hasAssignee: Optional[Assignee] = Field(default=None)
    hasIssueComment: Optional[IssueComment] = Field(default=None)
    isIssueOf: Optional[Repository] = Field(default=None)

class IssueComment(Property, RDFEntity):
    """
    GitHub Issue Comment
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/IssueComment'
    _property_uris: ClassVar[dict] = {'isIssueCommentOf': 'http://ontology.naas.ai/abi/github/isIssueCommentOf'}

    # Object properties
    isIssueCommentOf: Optional[Issue] = Field(default=None)

class PullRequest(Property, RDFEntity):
    """
    GitHub Pull Request
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/PullRequest'
    _property_uris: ClassVar[dict] = {'baseBranch': 'http://ontology.naas.ai/abi/github/baseBranch', 'headBranch': 'http://ontology.naas.ai/abi/github/headBranch', 'isPullRequestOf': 'http://ontology.naas.ai/abi/github/isPullRequestOf'}

    # Data properties
    baseBranch: Optional[str] = Field(default=None)
    headBranch: Optional[str] = Field(default=None)

    # Object properties
    isPullRequestOf: Optional[Repository] = Field(default=None)

class Contributor(Property, RDFEntity):
    """
    GitHub Contributor
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/Contributor'
    _property_uris: ClassVar[dict] = {'contributions': 'http://ontology.naas.ai/abi/github/contributions', 'isContributorOf': 'http://ontology.naas.ai/abi/github/isContributorOf'}

    # Data properties
    contributions: Optional[Any] = Field(default=None)

    # Object properties
    isContributorOf: Optional[Repository] = Field(default=None)

class RepositoryActivity(Property, RDFEntity):
    """
    GitHub Repository Activity
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/RepositoryActivity'
    _property_uris: ClassVar[dict] = {'activityType': 'http://ontology.naas.ai/abi/github/activityType', 'actor': 'http://ontology.naas.ai/abi/github/actor', 'isActivityOf': 'http://ontology.naas.ai/abi/github/isActivityOf'}

    # Data properties
    activityType: Optional[str] = Field(default=None)
    actor: Optional[str] = Field(default=None)

    # Object properties
    isActivityOf: Optional[Repository] = Field(default=None)

class Assignee(Property, RDFEntity):
    """
    GitHub Assignee
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/Assignee'
    _property_uris: ClassVar[dict] = {'isAssigneeOf': 'http://ontology.naas.ai/abi/github/isAssigneeOf'}

    # Object properties
    isAssigneeOf: Optional[Issue] = Field(default=None)

class Secret(Property, RDFEntity):
    """
    GitHub Repository Secret
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/Secret'
    _property_uris: ClassVar[dict] = {'isSecretOf': 'http://ontology.naas.ai/abi/github/isSecretOf', 'secretName': 'http://ontology.naas.ai/abi/github/secretName'}

    # Data properties
    secretName: Optional[str] = Field(default=None)

    # Object properties
    isSecretOf: Optional[Repository] = Field(default=None)

class Organization(Property, RDFEntity):
    """
    GitHub Organization
    """

    _class_uri: ClassVar[str] = 'http://ontology.naas.ai/abi/github/Organization'
    _property_uris: ClassVar[dict] = {'isOrganizationOf': 'http://ontology.naas.ai/abi/github/isOrganizationOf'}

    # Object properties
    isOrganizationOf: Optional[OrganizationPage] = Field(default=None)

# Rebuild models to resolve forward references
GitHubPage.model_rebuild()
Property.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b1.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b4.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b7.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b10.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b13.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b17.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b20.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b24.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b27.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b30.model_rebuild()
N7766f0aed17c489fa12dcb75722e24c2b38.model_rebuild()
UserPage.model_rebuild()
OrganizationPage.model_rebuild()
RepositoryPage.model_rebuild()
User.model_rebuild()
Repository.model_rebuild()
Issue.model_rebuild()
IssueComment.model_rebuild()
PullRequest.model_rebuild()
Contributor.model_rebuild()
RepositoryActivity.model_rebuild()
Assignee.model_rebuild()
Secret.model_rebuild()
Organization.model_rebuild()
