---
sidebar_position: 16
title: "Oxigraph as Local Development Triple Store"
---

# Oxigraph as Local Development Triple Store

- **Document Type:** ADR
- **Status:** Accepted
- **Date:** 2025-08-07

## Context

ABI needed a local triple store for development that did not require a running JVM or external Docker service. Blazegraph was the initially planned backend but was evaluated and rejected. The requirements were:

- Lightweight memory footprint for developer laptops.
- Native Apple Silicon (M1/M2/M3) support without emulation.
- Fast startup time for iterative development.
- Sufficient SPARQL 1.1 compliance for ABI's query patterns.
- Embeddable in-process or trivially runnable locally.

## Decision

Use **Oxigraph** as the local development triple store adapter, replacing Blazegraph:

| Criterion | Oxigraph | Blazegraph |
|-----------|----------|------------|
| Memory | ~50–100 MB | ~500 MB+ |
| Apple Silicon | Native | JVM only |
| Startup | < 1 second | 5–15 seconds |
| SPARQL compliance | 1.1 (full) | 1.1 (full) |
| Embedded mode | Yes | No |

Oxigraph is configured as the default when `ENVIRONMENT=local`. Production deployments use Apache Jena Fuseki TDB2 (see `20260212_apache-jena-fuseki-default-triplestore`).

## Consequences

### Positive
- Developers can run the full ABI stack locally without Docker.
- Near-instant triple store startup in dev.
- Native performance on Apple Silicon machines.

### Tradeoffs
- Oxigraph's on-disk format is not compatible with Fuseki TDB2; data cannot be directly migrated between environments.
- Some advanced Fuseki-specific features (e.g. SPARQL update transaction isolation) behave differently under Oxigraph.
- Two distinct triple store adapters must be maintained and tested in CI.
