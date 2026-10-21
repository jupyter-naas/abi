# PubMed

## What it is
- A small set of Pydantic models representing PubMed ontology entities.
- Each model instance can generate an `rdflib.Graph` of RDF triples via `rdf()`, including nested related objects.

## Public API

### `class RDFEntity(pydantic.BaseModel)`
Base class providing URI management and RDF graph generation.

- Class variables
  - `_namespace: ClassVar[str]` — default base namespace used to generate instance URIs (`"http://example.org/instance/"`).

- Instance attributes
  - `_uri: str` — instance URI. If not provided, auto-generated as `f"{_namespace}{uuid.uuid4()}"`.

- Methods
  - `set_namespace(namespace: str) -> None`  
    Set the namespace used for auto-generated URIs.
  - `rdf(subject_uri: str | None = None) -> rdflib.Graph`  
    Generate RDF triples for the instance:
    - Adds `(subject, rdf:type, _class_uri)` when `_class_uri` exists.
    - For each entry in `_property_uris`, emits predicate/object triples:
      - Related objects (having `.rdf`) are linked using their `._uri` and their triples are included.
      - Non-model values become `rdflib.Literal`.
      - Lists are supported: each item is emitted similarly.

### Ontology models (all inherit `RDFEntity`)
All models use Pydantic config:
- `extra='forbid'` (unknown fields are rejected)
- `arbitrary_types_allowed=True`

- `class PubMedPaperSummary(RDFEntity)`  
  Metadata summary returned by PubMed API for a single paper.
  - Data fields (all optional): `authorLiteral`, `doi`, `downloadUrl`, `journalTitleLiteral`, `pages`, `pmcid`, `publicationDate`, `pubmedIdentifier`, `sortPublicationDate`, `title`, `url`
  - Object fields (all optional): `aboutJournal: Journal`, `aboutJournalIssue: JournalIssue`, `hasAuthorshipRole: AuthorshipRole`, `summarizes: PubMedPaper`

- `class PubMedPaper(RDFEntity)`  
  Canonical description of a PubMed article.
  - Object fields (all optional): `hasAbstract: LiteralContent`, `hasKeyword: LiteralContent`, `hasMeshDescriptor: LiteralContent`, `publishedIn: JournalIssue`

- `class LiteralContent(RDFEntity)`  
  Holds literal text values.
  - Data field (optional): `literalValue`

- `class Journal(RDFEntity)`  
  Serial publication venue.
  - Data field (optional): `issn`

- `class JournalIssue(RDFEntity)`  
  Specific issue of a journal.
  - Data fields (optional): `issueLabel`, `volume`
  - Object field (optional): `issueOf: Journal`

- `class Author(RDFEntity)`  
  A human who bears an authorship role.

- `class AuthorshipRole(RDFEntity)`  
  Role held by a person when they author a PubMed paper.
  - Object field (optional): `roleHeldBy: Author`

## Configuration/Dependencies
- Dependencies:
  - `pydantic` (`BaseModel`, `Field`)
  - `rdflib` (`Graph`, `URIRef`, `Literal`, `rdflib.namespace.RDF`)
- Runtime behavior:
  - `_uri` can be provided at construction time via keyword `_uri=...`.
  - Forward references are resolved via `model_rebuild()` calls at module import time.

## Usage

```python
from naas_abi_marketplace.applications.pubmed.ontologies.PubMed import (
    RDFEntity, PubMedPaperSummary, PubMedPaper, LiteralContent,
    Journal, JournalIssue
)

# Optional: change base namespace for generated instance URIs
RDFEntity.set_namespace("http://my.example/instance/")

journal = Journal(issn="1234-5678")
issue = JournalIssue(volume="42", issueLabel="1", issueOf=journal)

paper = PubMedPaper(
    hasAbstract=LiteralContent(literalValue="Abstract text."),
    publishedIn=issue,
)

summary = PubMedPaperSummary(
    title="A paper",
    doi="10.0000/example",
    pubmedIdentifier="123456",
    aboutJournal=journal,
    aboutJournalIssue=issue,
    summarizes=paper,
)

g = summary.rdf()
print(len(g))
print(g.serialize())  # rdflib default serialization
```

## Caveats
- Unknown fields raise Pydantic validation errors (`extra='forbid'`).
- `rdf()` will emit non-model values as RDF literals; `downloadUrl` and `url` are typed as `Any` and will be serialized as literals unless you pass an object that has `.rdf()` and `._uri`.
- `rdf()` supports list-valued properties generically, but model fields are not typed as lists in this module; list usage must still satisfy Pydantic validation.
