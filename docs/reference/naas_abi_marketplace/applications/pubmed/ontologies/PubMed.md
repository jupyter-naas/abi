# PubMed (RDF/Pydantic Ontology Models)

## What it is
- A small set of Pydantic models representing a PubMed RDF ontology.
- Each model can generate an `rdflib.Graph` of RDF triples for the instance (and nested related instances) via `rdf()`.

## Public API

### Base class
- `class RDFEntity(BaseModel)`
  - Purpose: common RDF/URI behavior for all ontology entities.
  - Public attributes:
    - `_namespace: ClassVar[str]` (default: `http://example.org/instance/`) used to auto-generate instance URIs.
    - `_uri: str` instance URI (auto-generated if not provided).
  - Public methods:
    - `set_namespace(namespace: str) -> None`: set the namespace used for new auto-generated URIs.
    - `rdf(subject_uri: str | None = None) -> rdflib.Graph`: produce RDF triples for the instance.
      - Adds `rdf:type` using `_class_uri` (if present).
      - Adds property triples based on `_property_uris` (if present).
      - Recursively includes RDF for related objects that implement `.rdf()`.

### Ontology entity classes
All below inherit from `RDFEntity` and are Pydantic models with `extra='forbid'`.

- `class PubMedPaperSummary(RDFEntity)`
  - Purpose: metadata summary returned by the PubMed API for a single paper.
  - Data fields (optional):
    - `authorLiteral: str`
    - `doi: str`
    - `downloadUrl: Any`
    - `journalTitleLiteral: str`
    - `pages: str`
    - `pmcid: str`
    - `publicationDate: datetime.date`
    - `pubmedIdentifier: str`
    - `sortPublicationDate: datetime.datetime`
    - `title: str`
    - `url: Any`
  - Object fields (optional):
    - `aboutJournal: Journal`
    - `aboutJournalIssue: JournalIssue`
    - `hasAuthorshipRole: AuthorshipRole`
    - `summarizes: PubMedPaper`

- `class PubMedPaper(RDFEntity)`
  - Purpose: canonical description of a PubMed article.
  - Object fields (optional):
    - `hasAbstract: LiteralContent`
    - `hasKeyword: LiteralContent`
    - `hasMeshDescriptor: LiteralContent`
    - `publishedIn: JournalIssue`

- `class LiteralContent(RDFEntity)`
  - Purpose: holds literal text values.
  - Data fields (optional):
    - `literalValue: str`

- `class Journal(RDFEntity)`
  - Purpose: serial publication venue.
  - Data fields (optional):
    - `issn: str`

- `class JournalIssue(RDFEntity)`
  - Purpose: denotes a specific journal issue.
  - Data fields (optional):
    - `issueLabel: str`
    - `volume: str`
  - Object fields (optional):
    - `issueOf: Journal`

- `class Author(RDFEntity)`
  - Purpose: a human who bears an authorship role for a PubMed paper.
  - No declared fields/properties beyond `RDFEntity` internals.

- `class AuthorshipRole(RDFEntity)`
  - Purpose: a role held by a person when they author a PubMed paper.
  - Object fields (optional):
    - `roleHeldBy: Author`

## Configuration/Dependencies
- Python dependencies:
  - `pydantic` (models, validation)
  - `rdflib` (`Graph`, `URIRef`, `Literal`, `RDF`)
- Model configuration:
  - `arbitrary_types_allowed=True`
  - `extra='forbid'` (unknown fields raise validation errors)
- URIs:
  - If `_uri` is not provided, a URI is auto-generated as `f"{_namespace}{uuid.uuid4()}"`.
  - The RDF predicate URIs and class URIs are hard-coded per class via `_property_uris` and `_class_uri`.

## Usage

```python
from rdflib import Graph
from naas_abi_marketplace.applications.pubmed.ontologies.PubMed import (
    RDFEntity, PubMedPaperSummary, PubMedPaper, LiteralContent, Journal, JournalIssue
)

# Optional: set base namespace for generated instance URIs
RDFEntity.set_namespace("http://my.example/instance/")

journal = Journal(issn="1234-5678")
issue = JournalIssue(volume="42", issueLabel="1", issueOf=journal)

paper = PubMedPaper(
    hasAbstract=LiteralContent(literalValue="Abstract text."),
    publishedIn=issue
)

summary = PubMedPaperSummary(
    title="A paper",
    doi="10.0000/example",
    pubmedIdentifier="123456",
    aboutJournal=journal,
    aboutJournalIssue=issue,
    summarizes=paper
)

g: Graph = summary.rdf()
print(len(g))          # number of triples
print(g.serialize())   # default serialization (format chosen by rdflib)
```

## Caveats
- `rdf()` treats non-model values as RDF literals; object values are linked by their `._uri` and their own triples are included.
- Lists are supported in `rdf()` generation, but the ontology fields in this file are not typed as lists; passing lists may still work at runtime but must satisfy Pydantic validation (or use `Any`-typed fields).
- `downloadUrl` and `url` are typed as `Any` and will be emitted as RDF literals unless you supply an object that implements `.rdf()` (in which case it will be treated as a related RDF entity).
