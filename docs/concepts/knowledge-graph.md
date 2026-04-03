# Knowledge Graph and Ontologies

The knowledge graph is the structural core of ABI. Everything that agents know, query, and reason about lives here.

Related pages: [[building/creating-an-ontology|Creating an Ontology]], [[concepts/the-stack|The ABI Stack]], [[libs/naas-abi-core/services/Triple-Store|Triple Store Service]].

---

## What is the knowledge graph?

The knowledge graph is a triple store: a database of subject-predicate-object statements (triples) stored in RDF format and queryable with SPARQL.

Instead of a schema like `table: organizations (id, name, website)`, the knowledge graph uses:

```
<org/microsoft> rdf:type cco:CommercialOrganization .
<org/microsoft> abi:legalName "Microsoft Corporation" .
<org/microsoft> abi:hasLinkedInPage <page/microsoft-linkedin> .
```

This representation is:
- **Schema-flexible**: add new properties without migrations.
- **Relationship-native**: graph traversal is the default, not a join.
- **Reasoner-compatible**: OWL reasoners can infer new facts from axioms.
- **Interoperable**: RDF is an open standard; data can be exported, merged, or federated.

---

## The ontology hierarchy

ABI uses a layered ontology stack following the **Basic Formal Ontology (BFO)** standard (ISO/IEC 21838-2:2021):

```
BFO (Basic Formal Ontology)
└── CCO (Common Core Ontologies)
    ├── Enterprise Management Foundry    ← ABI built-in
    │   ├── Organizations, Persons, Roles
    │   ├── Products, Services, Markets
    │   ├── LinkedIn, Tickers, Brands
    │   └── Acts of merger, partnership, employment ...
    ├── Personal AI Foundry              ← ABI built-in
    │   └── Person-centric knowledge
    └── Your Domain Ontologies           ← built by you in modules
        └── Your Application Ontologies
```

Each layer extends the one above it. BFO provides universal categories (Continuant, Occurrent, Material Entity). CCO adds common mid-level concepts. ABI's built-in foundries add business concepts. Your module ontologies add what's specific to your domain.

### Why BFO?

BFO is an ISO standard used in defense, healthcare, finance, and intelligence. Grounding in BFO means:
- Your ontology is compatible with external datasets and standards.
- Reasoners behave predictably.
- You are not inventing naming conventions from scratch.

---

## Continuants vs. Occurrents

The most important BFO distinction:

| Category | Meaning | Examples |
|----------|---------|---------|
| **Continuant** | Things that persist through time | Person, Organization, Product, Role |
| **Occurrent** | Things that happen at a point in time | Act of Employment, Partnership, Acquisition |

Within Continuants:
- **Material entity**: has mass, physically exists (Person, Organization, Factory)
- **Generically dependent continuant**: information that can be copied (Brand, Legal Name, LinkedIn Page, Website)
- **Realizable entity**: capacities and roles (Skill, Capability, Role, Service)

This isn't academic. It determines how agents query and reason about your data. An "Act of Partnership" is an occurrent that links two organizations (continuants) at a specific time. SPARQL queries that ask "who was a partner of X between 2023 and 2025" are straightforward when this structure is enforced.

---

## How ontologies become code: onto2py

ABI includes `onto2py`, a code generation tool that reads OWL Turtle files and emits typed Python dataclasses alongside them.

```
# Your ontology file
libs/naas-abi/naas_abi/modules/crm/ontologies/
└── CRMOntology.ttl

# onto2py generates next to it:
└── CRMOntology.py   ← typed dataclasses, one per OWL class
```

This gives you a single source of truth: the `.ttl` file defines the RDF schema, and the generated `.py` file gives you type-checked Python access to ontology entities. No drift, no hand-written class definitions.

See [[building/creating-an-ontology|Creating an Ontology]] for usage.

---

## How agents use the knowledge graph

Agents interact with the knowledge graph in two ways:

1. **SPARQL queries as tools**: The `TemplatableSparqlQuery` built-in module lets you define parameterized SPARQL templates that agents invoke as tools - no Python required, just `.sparql` template files.

2. **Workflow queries**: Workflows call `engine.services.triple_store.query(sparql)` directly and process results as Python objects (via onto2py-generated classes).

---

## Supported triple store backends

| Backend | Use case | ADR |
|---------|---------|-----|
| Apache Jena Fuseki (TDB2) | Default for production and local dev | [[adr/20260212_apache-jena-fuseki-default-triplestore\|ADR-2026-02]] |
| Oxigraph | Alternative for lightweight local dev | [[adr/20250807_oxigraph-local-triplestore\|ADR-2025-08]] |
| AWS Neptune | Cloud-managed production | - |
| Filesystem | Dev/test without a running server | - |

Configuration is done in `config.yaml` under `services.triple_store`.
