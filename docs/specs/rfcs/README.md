# rfcs/

Request for Comments: written proposals for significant changes before a decision is made.

Write an RFC when you're proposing a new architecture, a breaking change, or a major capability and want to gather feedback first. Once the discussion settles, the decision gets recorded as an ADR in `../site/docs/updates/`.

## Index

| Date | RFC | Status |
|---|---|---|
| 2026-09-10 | [Distributed modules over NATS/JetStream](20260910_distributed-modules-nats-jetstream.md) | Draft |
| 2026-09-22 | [Remote agents and module dependencies](20260922_remote-agent-invocation.md) | First slice implemented |
| 2026-09-23 | [Remote module discovery](20260923_module-discovery.md) | First implementation delivered |
| 2026-10-13 | [Identity and authorization on the NATS engine](20261013_identity-and-authorization.md) | Accepted |

## Naming

`YYYYMMDD_short-title.md`, for example `20260405_agent-memory-backend.md`

## Template

```markdown
# RFC: <Title>

- **Date:** YYYY-MM-DD
- **Author:** <name>
- **Status:** Draft | Under Review | Accepted | Rejected | Superseded

## Problem

What are we trying to solve and why now?

## Proposal

What change do you propose and how does it work?

## Alternatives considered

What else was evaluated and why rejected?

## Open questions

What is still unresolved?
```
