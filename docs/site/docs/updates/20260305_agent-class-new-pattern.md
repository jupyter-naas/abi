---
sidebar_position: 4
title: "Agent.New() Class Method Pattern"
---

# Agent.New() Class Method Pattern

- **Document Type:** ADR
- **Status:** Accepted
- **Date:** 2026-03-05

## Context

Agents in ABI were instantiated via standalone `create_agent(...)` factory functions scattered across modules. This pattern had several problems:
- Factory functions were not colocated with the agent class, making discovery difficult.
- Agent initialization logic (intent registration, name validation, system prompt wiring) was duplicated or inconsistently applied across agents.
- There was no enforced contract for what a valid agent configuration looked like at construction time.

## Decision

Convert all agents from standalone `create_agent` factory functions to a `Agent.New()` class method pattern. Each agent class:
- Exposes a `New(...)` classmethod as its canonical constructor.
- Validates the agent name at construction time against a shared naming convention.
- Wires intents, system prompts, and tool lists as part of `New()`, ensuring they are always set consistently.
- Is colocated with its implementation, making the agent self-contained.

`AbiAgent` was refactored to a class-based implementation with enhanced initialization and is the base class all agents extend.

## Consequences

### Positive
- Agents are self-contained; no external factory function needed.
- Consistent initialization contract enforced at the class level.
- Name validation at construction time catches misconfigurations early.
- Easier to discover an agent's configuration by reading its class.

### Tradeoffs
- Existing callers using `create_agent(...)` required migration.
- `New()` is a non-standard Python convention; developers unfamiliar with the codebase may not expect it.
