# ADR: onto2py — Ontology-to-Python Code Generation

- Status: Accepted
- Date: 2026-01-27

## Context

ABI uses OWL ontologies (`.ttl` files) as the canonical schema for knowledge graph data. Developer workflows required writing Python classes to manipulate ontology instances by hand, creating drift between the ontology definition and the code that consumed it. Keeping class names, property names, and namespaces in sync across both representations was error-prone.

## Decision

Introduce `onto2py`: a code generation step that reads OWL Turtle files and emits typed Python dataclasses alongside each `.ttl` file. These generated classes are loaded on init so that downstream code (agents, pipelines, SPARQL queries) references ontology-backed Python types rather than raw strings.

Key behaviors:
- Generation runs at module load time and on explicit CLI invocation.
- Each generated class reflects the `rdfs:label`, `owl:ObjectProperty`, and `owl:DatatypeProperty` declarations in the ontology.
- Class and property names follow PascalCase/camelCase conventions derived from the ontology labels.
- `owl:hasKey` annotations are used to drive entity resolution and deduplication logic.

## Consequences

### Positive
- Single source of truth: the ontology drives both the RDF schema and the Python API.
- Eliminates manual class/property drift.
- Enables type-checked usage of ontology entities in agents and pipelines.

### Tradeoffs
- Generated files must be re-run after ontology changes; stale generated code will compile but produce incorrect RDF.
- Generated classes are checked in alongside `.ttl` files, increasing repo noise for ontology-heavy modules.
- Code generation adds a startup-time cost on first load.
