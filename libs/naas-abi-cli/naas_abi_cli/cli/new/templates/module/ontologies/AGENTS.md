# `ontologies/` — AGENTS.md

> Scope: ontology definitions for the `{{module_name_snake}}` module. See the module's [AGENTS.md](../AGENTS.md) for module-wide context.

## What goes here

**RDF / OWL** schemas that describe the vocabulary your module reasons over — classes, properties, named individuals, axioms. These TTL files are the single source of truth for the module's domain model.

`BaseModule.on_load()` auto-loads every `.ttl` file in this directory into the `TripleStoreService` as a **schema graph**, and `onto2py` can generate Python classes (under `classes/`) from them for type-safe RDF construction.

## File shape

Files are `PascalCase`, one schema per file: `<Topic>.ttl`. Use Turtle syntax with explicit prefixes.

```turtle
@prefix : <http://ontology.naas.ai/{{module_name_snake}}/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix cco: <https://www.commoncoreontologies.org/> .

<http://ontology.naas.ai/{{module_name_snake}}/{{module_name_snake}}> a owl:Ontology ;
    owl:imports <http://purl.obolibrary.org/obo/bfo.owl> .

:MyClass a owl:Class ;
    rdfs:subClassOf bfo:BFO_0000001 ;
    rdfs:label "My Class"@en ;
    rdfs:comment "..."@en .

:myProperty a owl:DatatypeProperty ;
    rdfs:domain :MyClass ;
    rdfs:range xsd:string .
```

## Conventions

- **Import upper ontologies** (`BFO`, `CCO`) where applicable — see [`.abi/libs/naas-abi-core/.../modules/bfo/`](../../../.abi/libs/naas-abi-core/naas_abi_core/modules/bfo) and [`.../modules/cco/`](../../../.abi/libs/naas-abi-core/naas_abi_core/modules/cco). Don't reinvent classes that already exist there.
- **Use stable IRIs** under `http://ontology.naas.ai/{{module_name_snake}}/`. Once published, never repurpose an IRI.
- **One topic per file** — `Customer.ttl`, `Order.ttl`, etc. Easier to diff and review.
- **English labels and comments** (`@en`) on every class and property.
- **Named individuals** (instances) belong in `classes/` (auto-generated) or in pipeline output — keep TTL files schema-only.

## Generated Python classes

`onto2py` generates Python wrappers from TTLs:

```
ontologies/
├── <Topic>.ttl                 # hand-edited schema
└── classes/                    # generated — do NOT hand-edit
    └── ontology_naas_ai/
        └── {{module_name_snake}}/
            └── MyClass.py
```

To regenerate after a TTL change:

```bash
uv run python -m naas_abi_core.utils.onto2py {{module_name_snake}}/ontologies
```

Treat `classes/` as build output — commit it for IDE completion, but never hand-edit it.

## Loading & querying

At module load, every TTL here is registered with `TripleStoreService.load_schema(...)` and becomes queryable through SPARQL alongside other modules' schemas.

In pipelines / workflows:

```python
from rdflib import Graph, RDF, URIRef
from {{module_name_snake}}.ontologies.classes.ontology_naas_ai.{{module_name_snake}}.MyClass import MyClass

instance = MyClass(label="foo")
g = instance.to_graph()
triple_store.insert(g, graph_name=URIRef("..."))
```

## Tests

Optional but recommended — verify the TTL parses and the expected classes are present:

```python
from rdflib import Graph
from pathlib import Path

def test_ontology_parses():
    g = Graph()
    g.parse(Path(__file__).parent / "MyTopic.ttl", format="turtle")
    assert len(g) > 0
```

Run:

```bash
uv run pytest {{module_name_snake}}/ontologies
```

## Wiring into the module

1. Declare `TripleStoreService` in `ABIModule.dependencies.services`.
2. `BaseModule.on_load()` auto-discovers and loads every `.ttl` here — no manual `load_schema` calls needed.
3. Pipelines / workflows that emit triples should use this ontology's classes (or URIs) as the target vocabulary.

## See also

- Triple store service (schema loading, SPARQL, views): [`.abi/libs/naas-abi-core/.../services/triple_store/AGENTS.md`](../../../.abi/libs/naas-abi-core/naas_abi_core/services/triple_store/AGENTS.md)
- Ontology NER service: [`.abi/libs/naas-abi-core/.../services/ontology/AGENTS.md`](../../../.abi/libs/naas-abi-core/naas_abi_core/services/ontology/AGENTS.md)
- BFO / CCO upper ontologies: [`.abi/.../modules/bfo/`](../../../.abi/libs/naas-abi-core/naas_abi_core/modules/bfo), [`.abi/.../modules/cco/`](../../../.abi/libs/naas-abi-core/naas_abi_core/modules/cco)
- `onto2py` generator: [`.abi/.../utils/onto2py/`](../../../.abi/libs/naas-abi-core/naas_abi_core/utils/onto2py)
