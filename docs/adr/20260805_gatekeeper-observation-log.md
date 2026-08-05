# ADR: Gatekeeper and Observation Log

## Status

Accepted — 2026-08-05

## Context

Cloudflare OS demonstrated that MCP tool lists alone are insufficient for enterprise agent governance. Agents can observe sensitive data through tool calls, and sharing conversations or exports can become an exfiltration path unless policy follows observed resources.

Abi already has:

- Nexus IAM (workspace roles, JWT scopes)
- Agent event publishing (`AgentToolCalled`, etc.)
- Marketplace integrations that call third-party APIs directly
- Owner-scoped chat conversations

What was missing: a mediation layer between agents and integrations that enforces default-deny for sensitive operations, records provenance, and applies derivation checks before export.

## Decision

Introduce a **Gatekeeper service** in `naas_abi_core.services.gatekeeper`:

1. **Port + service** following the same pattern as `activity_log` and `event`.
2. **SQLite adapter** for observations and per-chat session grants.
3. **GitHub pilot policy** — secret-read and destructive repo tools require explicit session grants on `github.repo` resources.
4. **Agent hook** in `Agent.call_tools` — evaluate before invoke, record after success.
5. **Derivation check** in Nexus chat export — deny when sensitive observations exist and the viewer lacks export grants.
6. **Process-wide accessor** via `get_default_gatekeeper_service()`, initialized on `Engine.load()`.

## Consequences

### Positive

- Sensitive GitHub tools are blocked without explicit grants (Cloudflare OS “agents start with no access” for high-risk operations).
- Every gated tool call leaves an observation tied to `chat_id` for audit and export policy.
- Export path demonstrates “policy follows what the agent has seen.”
- Hexagonal layout allows additional integration policies without changing Agent core.

### Negative / follow-ups

- No grant UI yet — grants are programmatic (`grant_resource`) until Nexus adds an approval flow.
- Only GitHub is policy-wrapped; other marketplace integrations still call APIs directly.
- Conversation **read** remains owner-scoped; cross-user shared threads need IAM + gatekeeper extension.
- Gatekeeper is not yet wired into full Engine service configuration (uses default SQLite path).

## References

- https://blog.cloudflare.com/cloudflare-os/
- GitHub issue #1171
- `libs/naas-abi-core/naas_abi_core/services/gatekeeper/AGENTS.md`
