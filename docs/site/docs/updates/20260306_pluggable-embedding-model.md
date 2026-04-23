---
sidebar_position: 2
title: "Pluggable Embedding Model Support"
---

# Pluggable Embedding Model Support

- **Document Type:** ADR
- **Status:** Accepted
- **Date:** 2026-03-06

## Context

ABI's vector store and semantic search features relied on a hardcoded embedding model. This prevented:
- Using cheaper/faster models for lower-stakes embeddings.
- Switching to domain-specific embedding models for specialized corpora.
- Supporting deployments that cannot call OpenAI's embedding API (air-gapped, cost-constrained, or compliance-restricted environments).

## Decision

Make the embedding model configurable by allowing callers to inject their own embedding model instance when initializing the vector store service and any component that performs embedding (agents, pipelines, search workflows).

The interface contract is minimal: any object that exposes an `embed(text: str) -> list[float]` compatible method can be used. The default remains the OpenAI embedding model. Configuration is done at the module level in `config.yaml` under the vector store service section.

## Consequences

### Positive
- Deployments can optimize cost and latency by choosing an appropriate embedding model.
- Enables offline or self-hosted embedding (e.g. local sentence-transformers) without code changes.
- Easier to test embedding-dependent logic with a deterministic mock model.

### Tradeoffs
- Embedding model consistency is now the operator's responsibility: changing models on an existing index invalidates all stored vectors and requires a full re-index.
- No automatic detection or warning when the configured model diverges from the model used to build the existing index.
