from __future__ import annotations

import datetime
import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field
from rdflib import Graph, Literal, URIRef
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


class PubMedPaperSummary(RDFEntity):
    """
    A generically dependent continuant that encodes the metadata summary returned by the PubMed API for a single paper.
    """

    _class_uri: ClassVar[str] = 'https://w3id.org/pubmed/PubMedPaperSummary'
    _property_uris: ClassVar[dict] = {'aboutJournal': 'https://w3id.org/pubmed/aboutJournal', 'aboutJournalIssue': 'https://w3id.org/pubmed/aboutJournalIssue', 'authorLiteral': 'https://w3id.org/pubmed/authorLiteral', 'doi': 'https://w3id.org/pubmed/doi', 'downloadUrl': 'https://w3id.org/pubmed/downloadUrl', 'hasAuthorshipRole': 'https://w3id.org/pubmed/hasAuthorshipRole', 'journalTitleLiteral': 'https://w3id.org/pubmed/journalTitleLiteral', 'pages': 'https://w3id.org/pubmed/pages', 'pmcid': 'https://w3id.org/pubmed/pmcid', 'publicationDate': 'https://w3id.org/pubmed/publicationDate', 'pubmedIdentifier': 'https://w3id.org/pubmed/pubmedIdentifier', 'sortPublicationDate': 'https://w3id.org/pubmed/sortPublicationDate', 'summarizes': 'https://w3id.org/pubmed/summarizes', 'title': 'https://w3id.org/pubmed/title', 'url': 'https://w3id.org/pubmed/url'}

    # Data properties
    authorLiteral: str | None = Field(default=None)
    doi: str | None = Field(default=None)
    downloadUrl: Any | None = Field(default=None)
    journalTitleLiteral: str | None = Field(default=None)
    pages: str | None = Field(default=None)
    pmcid: str | None = Field(default=None)
    publicationDate: datetime.date | None = Field(default=None)
    pubmedIdentifier: str | None = Field(default=None)
    sortPublicationDate: datetime.datetime | None = Field(default=None)
    title: str | None = Field(default=None)
    url: Any | None = Field(default=None)

    # Object properties
    aboutJournal: Journal | None = Field(default=None)
    aboutJournalIssue: JournalIssue | None = Field(default=None)
    hasAuthorshipRole: AuthorshipRole | None = Field(default=None)
    summarizes: PubMedPaper | None = Field(default=None)

class PubMedPaper(RDFEntity):
    """
    The information content entity representing the canonical description of a PubMed article.
    """

    _class_uri: ClassVar[str] = 'https://w3id.org/pubmed/PubMedPaper'
    _property_uris: ClassVar[dict] = {'hasAbstract': 'https://w3id.org/pubmed/hasAbstract', 'hasKeyword': 'https://w3id.org/pubmed/hasKeyword', 'hasMeshDescriptor': 'https://w3id.org/pubmed/hasMeshDescriptor', 'publishedIn': 'https://w3id.org/pubmed/publishedIn'}

    # Object properties
    hasAbstract: LiteralContent | None = Field(default=None)
    hasKeyword: LiteralContent | None = Field(default=None)
    hasMeshDescriptor: LiteralContent | None = Field(default=None)
    publishedIn: JournalIssue | None = Field(default=None)

class LiteralContent(RDFEntity):
    """
    An information content entity that holds literal text values.
    """

    _class_uri: ClassVar[str] = 'https://w3id.org/pubmed/LiteralContent'
    _property_uris: ClassVar[dict] = {'literalValue': 'https://w3id.org/pubmed/literalValue'}

    # Data properties
    literalValue: str | None = Field(default=None)

class Journal(RDFEntity):
    """
    A serial publication venue that bears PubMed papers.
    """

    _class_uri: ClassVar[str] = 'https://w3id.org/pubmed/Journal'
    _property_uris: ClassVar[dict] = {'issn': 'https://w3id.org/pubmed/issn'}

    # Data properties
    issn: str | None = Field(default=None)

class JournalIssue(RDFEntity):
    """
    A generically dependent continuant denoting a specific issue of a journal.
    """

    _class_uri: ClassVar[str] = 'https://w3id.org/pubmed/JournalIssue'
    _property_uris: ClassVar[dict] = {'issueLabel': 'https://w3id.org/pubmed/issueLabel', 'issueOf': 'https://w3id.org/pubmed/issueOf', 'volume': 'https://w3id.org/pubmed/volume'}

    # Data properties
    issueLabel: str | None = Field(default=None)
    volume: str | None = Field(default=None)

    # Object properties
    issueOf: Journal | None = Field(default=None)

class Author(RDFEntity):
    """
    A human who bears an authorship role for a PubMed paper.
    """

    _class_uri: ClassVar[str] = 'https://w3id.org/pubmed/Author'
    _property_uris: ClassVar[dict] = {}

class AuthorshipRole(RDFEntity):
    """
    A role inhering in a person when they author a PubMed paper.
    """

    _class_uri: ClassVar[str] = 'https://w3id.org/pubmed/AuthorshipRole'
    _property_uris: ClassVar[dict] = {'roleHeldBy': 'https://w3id.org/pubmed/roleHeldBy'}

    # Object properties
    roleHeldBy: Author | None = Field(default=None)

# Rebuild models to resolve forward references
PubMedPaperSummary.model_rebuild()
PubMedPaper.model_rebuild()
LiteralContent.model_rebuild()
Journal.model_rebuild()
JournalIssue.model_rebuild()
Author.model_rebuild()
AuthorshipRole.model_rebuild()
