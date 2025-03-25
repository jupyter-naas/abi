# Pipelines Architecture

Pipelines in ABI are specialized components that ingest data from external sources, transform it into semantic triples, and populate the knowledge graph (ontology). They serve as the bridge between raw data and the unified semantic representation.

## Design Philosophy

Pipelines are designed to be:
1. **Transformation-focused**: Convert external data into ontological representation
2. **Integration-dependent**: Use integrations to access external data
3. **Ontology-aware**: Understand the semantic model and triplet structure
4. **Deterministic**: Produce consistent output for the same input

