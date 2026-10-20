# Creating an Ontology

Ontologies are the schema layer of ABI's knowledge graph. They define classes, properties, and axioms in OWL Turtle format. `onto2py` then generates typed Python classes from them.

Ontologies live in a module's `ontologies/` folder, and the engine loads them into the triple store when it loads the module. They therefore belong in an [in-engine module](/user-guide/build/modules/creating-a-module#remote-or-in-engine).

---

## Design before you code

Before writing Turtle, answer these questions:

1. **What entities do you model?** (Continuants: organizations, persons, products)
2. **What events/processes do you model?** (Occurrents: acts of partnership, employment, purchase)
3. **What properties link them?** (Object properties: `hasOwner`, `isPartOf`)
4. **What data properties do they carry?** (Datatype properties: `name`, `url`, `externalId`)
5. **What upper ontology classes do they extend?** (ABI's `abi:` classes, CCO classes, BFO categories)

Do not create a class that already exists in BFO or CCO. Look it up first, and keep a module-local name with `owl:equivalentClass` or `rdfs:subClassOf` pointing at the CCO class, so your pipelines keep stable Python names.

---

## The seven buckets

Every class must trace to one of the seven BFO buckets, or `onto2py` refuses to generate code for it. Subclass the matching `abi:` class and the trace comes with it:

| Bucket | Question | Subclass |
|---|---|---|
| WHAT | what is happening | `abi:Process` |
| WHEN | over what interval | `abi:TemporalRegion` |
| WHO | which participant | `abi:MaterialEntity`, `abi:Person` |
| WHERE | at what place | `abi:Site` |
| HOW WE KNOW | which record | `abi:GenericallyDependentContinuant` |
| HOW IT IS | which quality | `abi:Quality` |
| WHY | which role or disposition | `abi:Role`, `abi:Disposition` |

Qualities, roles and dispositions must carry an `abi:inheresIn` restriction that names their bearer; the validator rejects them otherwise. Use the `abi:` properties (`abi:hasParticipant`, `abi:occursIn`, `abi:concretizes`, `abi:inheresIn`, ...) rather than raw `bfo:` ones, so their inverses carry over.

---

## Ontology file structure

`abi new module <name> --in-engine` scaffolds the layout, with a starter file in each folder:

```bash
src/my_module/ontologies/
├── modules/
│   └── MyModuleOntology.ttl      # shared classes and properties; owl:imports each process
├── processes/
│   └── MyModuleProcess.ttl       # one BFO process slice per file
└── queries/
    └── MyModuleSparqlQueries.ttl # templatable SPARQL queries, turned into agent tools
```

`onto2py` writes the generated Python next to each Turtle file (`MyModuleOntology.py`), and action-class stubs under `classes/`. Commit them; do not edit them by hand. The module loads every `*.ttl` under `ontologies/`, recursively, into the triple store when the engine starts. Anything in these files lands in the live triple store, so keep named individuals out: they belong in pipeline output.

---

## Writing a Turtle file

A module ontology declares itself, imports the ABI ontology, and then defines properties and classes. This is the shape of the scaffolded `modules/MyModuleOntology.ttl` (abridged):

```turtle
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix abi:  <http://ontology.naas.ai/abi/> .
@prefix my_module: <http://ontology.naas.ai/my_module/> .

my_module:MyModuleOntology a owl:Ontology ;
  # One owl:imports statement per IRI, never a comma-separated list.
  owl:imports <http://ontology.naas.ai/abi/Ontology> ;
  owl:imports <http://ontology.naas.ai/abi/PersonOntology> ;
  # Locator annotations: other modules resolve this ontology to Python through them.
  abi:pythonPackage "my_module" ;
  abi:ontologyResource "ontologies/modules/MyModuleOntology.ttl" ;
  abi:pythonResource "ontologies/modules/MyModuleOntology.py" .

# Pair every relation with its inverse, and subclass an abi: relation.
my_module:hasRecord a owl:ObjectProperty ;
    rdfs:subPropertyOf abi:isCarrierOf ;
    owl:inverseOf my_module:isRecordOf ;
    rdfs:label "has record"@en ;
    skos:definition "Relates a person to a record that generically depends on them."@en ;
    rdfs:domain abi:Person ;
    rdfs:range my_module:MyModuleRecord .

my_module:record_id a owl:DatatypeProperty ;
    rdfs:label "record id"@en ;
    skos:definition "Identifier of the record in the source system."@en ;
    rdfs:domain my_module:MyModuleRecord ;
    rdfs:range xsd:string .

# HOW WE KNOW: a record about something
my_module:MyModuleRecord a owl:Class ;
    rdfs:subClassOf abi:GenericallyDependentContinuant ,
      [ a owl:Restriction ; owl:onProperty my_module:isRecordOf ; owl:someValuesFrom abi:Person ] ;
    rdfs:label "My Module Record"@en ;
    skos:definition "An information content entity that documents something about a person."@en ;
    skos:example "A record with the identifier 12345 in the source system."@en .
```

A process file in `processes/` imports the module ontology (never the reverse), defines only its process class, process-only properties and restrictions on shared IRIs, and gives the process one restriction per bucket it touches. Open the scaffolded `MyModuleProcess.ttl` for the pattern.

---

## onto2py code generation

`onto2py` reads a `.ttl` file and writes a Python file next to it. Run it for the process files first, then the module ontology (the module run validates the combined graph):

```bash
ABI_SKIP_ONTOLOGY_CHECK=1 uv run python -m naas_abi_core.utils.onto2py \
    src/my_module/ontologies/processes/MyModuleProcess.ttl
uv run python -m naas_abi_core.utils.onto2py \
    src/my_module/ontologies/modules/MyModuleOntology.ttl
```

`ABI_SKIP_ONTOLOGY_CHECK=1` skips the standalone check for process files, which restrict shared IRIs that are declared elsewhere. A `could not resolve owl:imports` warning for the CCO and BFO imports is expected: the TTL still loads in full. In the ABI repository, `make onto2py` regenerates every file under `libs/`.

The generated file holds one Pydantic model per class, with a field per data property (in snake case) and an `rdf()` method that returns the entity's triples:

```python
# Auto-generated - do not edit manually
class MyModuleRecord(..., RDFEntity):  # its parent classes, then the base entity
    """
    An information content entity that documents something about a person.
    """

    record_id: Annotated[str, Field(description="Identifier of the record in the source system.")] | None = None
```

```python
from my_module.ontologies.modules.MyModuleOntology import MyModuleRecord

record = MyModuleRecord(record_id="12345")
graph = record.rdf()   # an rdflib.Graph
```

Generation is a step you run, not something the engine does at load: the engine loads the `.ttl` files, and imports the generated `.py` files only when your code does. Run `onto2py` after each change to a Turtle file and commit the result. See [Creating a Pipeline](/user-guide/build/knowledge-graph/creating-a-pipeline#using-onto2py-generated-classes) for the classes in use.

---

## Ontology best practices

1. **Start with existing classes**: reuse BFO, CCO and `abi:` classes before minting your own.
2. **One concept per class**: keep classes focused; avoid "God classes" with many unrelated properties.
3. **Document everything**: `rdfs:label`, `skos:definition`, and `skos:example` for every class and property. Agents use these descriptions.
4. **Pair every relation with its inverse**, and subclass an `abi:` relation.
5. **Stable IRIs** under `http://ontology.naas.ai/<module>/`.
6. **Separate shared vocabulary from processes**: shared classes in `modules/`, one process per file in `processes/`.
7. **Backward compatible updates**: adding new classes/properties is safe. Removing or renaming requires a migration.

---

## Loading verification

After adding or editing an ontology file, restart the engine, then query the triple store for your class. Ontologies are loaded into the graph `http://ontology.naas.ai/graph/schema`. With `abi dev up`, `abi dev ports` prints the triple store's port (`oxigraph`):

```bash
curl -s -X POST "http://localhost:<oxigraph-port>/query" \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  --data 'SELECT ?class WHERE { GRAPH <http://ontology.naas.ai/graph/schema> {
      ?class a <http://www.w3.org/2002/07/owl#Class>
      FILTER(STRSTARTS(STR(?class), "http://ontology.naas.ai/my_module/")) } }'
```

Your new class should appear. With the Docker stack the triple store is Fuseki (http://localhost:3030); the Nexus ontology and graph pages show the same data.
