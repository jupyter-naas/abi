---
sidebar_position: 7
title: "Apache Jena Fuseki TDB2 as Default Triple Store"
---

# Apache Jena Fuseki TDB2 as Default Triple Store

- **Document Type:** ADR
- **Status:** Accepted
- **Date:** 2026-02-12

## Context

ABI's knowledge graph requires reliable SPARQL update support with ACID transaction guarantees. The existing adapters (filesystem, Oxigraph, AWS Neptune) each had gaps:
- The filesystem adapter has no transactional semantics.
- Oxigraph is lightweight but lacks full named graph operation support and is not production-proven at scale.
- AWS Neptune is cloud-only and requires VPC setup, making local development impractical.

A shared, generic adapter test suite was also missing, making it hard to validate behavioral parity across implementations.

## Decision

Add Apache Jena Fuseki with TDB2 as a first-class secondary adapter for `TripleStoreService` and make it the default in local development and production deployment templates.

Key design choices:
- Named graph operations (`create`, `clear`, `remove`, `insert`, `query`) are defined at the port interface level so all adapters must implement them.
- A reusable generic adapter test class validates consistent behavior across all triple store implementations.
- Integration tests for Jena and Oxigraph are wired into CI on pull requests.
- Local deploy templates default to Fuseki (`docker compose up -d fuseki`).

## Consequences

### Positive
- ACID-compliant SPARQL transactions via TDB2.
- Full named graph support with a consistent interface across adapters.
- Shared test class ensures new adapters can be validated without writing tests from scratch.

### Tradeoffs
- Fuseki requires a running Docker container; purely offline development needs the filesystem adapter fallback.
- TDB2 on-disk format is not portable across Jena versions without a migration step.
- Adds a JVM dependency to the infrastructure stack.
