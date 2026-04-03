---
sidebar_position: 13
title: "Intent Scope for Controlled Agent Routing"
---

# Intent Scope for Controlled Agent Routing

- **Document Type:** ADR
- **Status:** Accepted
- **Date:** 2025-09-25

## Context

The SupervisorAgent routes user messages to specialized agents based on registered intents. As the number of agents grew (integration agents, research agents, domain-specific agents), all of them were visible to the supervisor by default. This caused:

- Research/experimental agents being routed to for production queries they were not designed for.
- Integration agents (which require live API credentials) being surfaced in environments where those credentials were absent.
- Intent collision: agents with overlapping domains competed for the same user queries, degrading routing accuracy.

## Decision

Introduce **intent scope** as a first-class property on agents and intents. Each agent declares a scope that controls whether it is included in the supervisor's routing table:

- **`supervisor`** - visible to the supervisor for general user query routing (default).
- **`integration`** - available for direct invocation but excluded from the supervisor's default routing.
- **`research`** - excluded from the supervisor; used for exploration and not production routing.

Agents can also declare `exclude_from_supervisor: bool` as a simpler binary control. The supervisor's intent table is built at startup by filtering agents to only those with `supervisor` scope.

## Consequences

### Positive
- Supervisor routing table stays focused and accurate as agent count grows.
- Research and integration agents can be developed and registered without polluting production routing.
- Scope is declarative and colocated with the agent definition.

### Tradeoffs
- Agents with `integration` or `research` scope are only accessible if the caller knows to invoke them directly.
- Scope is set at definition time; dynamic scope changes at runtime are not supported.
- New agents default to `supervisor` scope, meaning developers must explicitly opt out for non-production agents.
