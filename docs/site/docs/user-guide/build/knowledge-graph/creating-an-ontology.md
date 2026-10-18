# Creating an Ontology

Ontologies are the schema layer of ABI's knowledge graph. They define classes, properties, and axioms in OWL Turtle format. `onto2py` then generates typed Python classes from them automatically.

---

## Design before you code

Before writing Turtle, answer these questions:

1. **What entities do you model?** (Continuants: organizations, persons, products)
2. **What events/processes do you model?** (Occurrents: acts of partnership, employment, purchase)
3. **What properties link them?** (Object properties: `hasOwner`, `isPartOf`)
4. **What data properties do they carry?** (Datatype properties: `name`, `url`, `externalId`)
5. **What upper ontology classes do they extend?** (CCO classes, BFO categories)

Do not create a class that already exists in BFO or CCO. Look it up first.

---

## BFO quick reference

| Your entity | BFO/CCO class to extend |
|------------|------------------------|
| A company, organization, or team | `cco:CommercialOrganization` or `cco:Organization` |
| A person | `cco:Person` |
| A digital information artifact (page, document, record) | `cco:InformationContentEntity` |
| A role someone plays | `cco:OrganizationalRole` |
| A capability or skill | `cco:Capability` |
| A product or service | `cco:Product` / `cco:Service` |
| An act that happens at a time | `bfo:Process` (Occurrent) |

---

## Ontology file structure

Place ontology files in your module's `ontologies/` directory:

```bash
naas_abi/modules/custom/my_module/ontologies/
├── MyDomainOntology.ttl       # Domain-level classes
└── MyApplicationOntology.ttl  # Module-specific classes
```

---

## Writing a Turtle file

```turtle
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dc:   <http://purl.org/dc/elements/1.1/> .
@prefix bfo:  <http://purl.obolibrary.org/obo/> .
@prefix cco:  <https://www.commoncoreontologies.org/> .
@prefix abi:  <http://ontology.naas.ai/abi/> .

# ── Ontology declaration ──────────────────────────────────────────

<http://ontology.naas.ai/abi/my_module.ttl>
    rdf:type owl:Ontology ;
    dc:title "My Module Ontology" ;
    dc:description "Domain ontology for my module."@en ;
    dc:contributor "Your Name" .

# ── Classes ───────────────────────────────────────────────────────

abi:MyEntity a owl:Class ;
    rdfs:subClassOf cco:InformationContentEntity ;
    rdfs:label "My Entity"@en ;
    skos:definition "An entity that represents [describe what it is]."@en ;
    skos:example "Example: [give a concrete example]."@en .

# ── Object Properties ─────────────────────────────────────────────

abi:hasMyEntity a owl:ObjectProperty ;
    rdfs:domain cco:Organization ;
    rdfs:range abi:MyEntity ;
    owl:inverseOf abi:isMyEntityOf ;
    rdfs:label "has my entity"@en ;
    skos:definition "Relates an organization to its associated entity."@en .

abi:isMyEntityOf a owl:ObjectProperty ;
    rdfs:domain abi:MyEntity ;
    rdfs:range cco:Organization ;
    owl:inverseOf abi:hasMyEntity ;
    rdfs:label "is my entity of"@en .

# ── Datatype Properties ───────────────────────────────────────────

abi:externalId a owl:DatatypeProperty ;
    rdfs:domain abi:MyEntity ;
    rdfs:range xsd:string ;
    rdfs:label "external ID"@en ;
    skos:definition "The unique ID of this entity in the external system."@en ;
    skos:example "The ID '12345' from MyService's API response."@en .

abi:externalUrl a owl:DatatypeProperty ;
    rdfs:domain abi:MyEntity ;
    rdfs:range xsd:string ;
    rdfs:label "external URL"@en ;
    skos:definition "The URL of this entity in the external system."@en .
```

---

## onto2py code generation

`onto2py` reads your `.ttl` file and generates a Python file alongside it:

```bash
# Run manually
uv run python -m naas_abi_core.utils.onto2py.onto2py \
    naas_abi/modules/custom/my_module/ontologies/MyApplicationOntology.ttl
```

This generates `MyApplicationOntology.py` with typed dataclasses:

```python
# Auto-generated - do not edit manually
from dataclasses import dataclass, field
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS

ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class MyEntity:
    uri: str
    label: str | None = None
    external_id: str | None = None
    external_url: str | None = None

    def to_graph(self) -> Graph:
        g = Graph()
        subject = URIRef(self.uri)
        g.add((subject, RDF.type, ABI.MyEntity))
        if self.label:
            g.add((subject, RDFS.label, Literal(self.label)))
        if self.external_id:
            g.add((subject, ABI.externalId, Literal(self.external_id)))
        if self.external_url:
            g.add((subject, ABI.externalUrl, Literal(self.external_url)))
        return g
```

Generation also runs automatically at module load time.

---

## Ontology best practices

1. **Start with existing classes**: never create `abi:Organization` when `cco:CommercialOrganization` already exists.
2. **One concept per class**: keep classes focused; avoid "God classes" with many unrelated properties.
3. **Document everything**: `rdfs:label`, `skos:definition`, and `skos:example` are required for every class and property. Agents use these descriptions.
4. **Naming conventions**: `ClassNamesInPascalCase`, `objectPropertyNamesInCamelCase`, `datatypePropertyNamesInLowerCamelCase`.
5. **Separate domain from application**: domain ontologies (`cco:Organization`-level) in one file, application-specific classes (LinkedIn page, Salesforce record) in another.
6. **Backward compatible updates**: adding new classes/properties is safe. Removing or renaming requires a migration.

---

## Loading verification

After adding or editing an ontology file, restart the Engine and verify the triple store:

```bash
make sparql-terminal
```

Then query:

```sparql
SELECT ?class WHERE {
    ?class a owl:Class .
    FILTER(STRSTARTS(STR(?class), "http://ontology.naas.ai/abi/"))
}
```

Your new class should appear.
