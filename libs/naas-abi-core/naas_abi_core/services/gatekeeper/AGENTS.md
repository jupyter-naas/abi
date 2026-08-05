# Gatekeeper Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/gatekeeper/`. Canonical reference for agents.

## Purpose

Mediate agent tool access to external systems, record observations for provenance, and enforce derivation policy when conversations or exports are shared.

Inspired by Cloudflare OS Gatekeepers: agents start without broad integration access; sensitive operations require explicit session grants; policy follows observed data.

## Files

```
gatekeeper/
├── GatekeeperPort.py              # DTOs + IObservationStore / IGrantStore / IGatekeeperDomain
├── GatekeeperService.py           # evaluate_tool_call, record_tool_observation, export policy
├── GatekeeperFactory.py
├── policies/
│   └── GitHubGatekeeperPolicy.py  # Pilot: GitHub secret + delete-repo tools
├── adapters/secondary/
│   └── GatekeeperSqliteAdapter.py
└── GatekeeperService_test.py
```

## Port

```python
evaluate_tool_call(subject, tool_name, tool_args) -> GatekeeperDecision
record_tool_observation(subject, tool_name, tool_args) -> ObservationRecord | None
grant_resource(chat_id, resource, actions) -> ResourceGrant
evaluate_conversation_export(subject, conversation_id) -> GatekeeperDecision
list_observations(chat_id) -> list[ObservationRecord]
```

## Pilot policy (GitHub)

**Prerequisites:** GitHub must be enabled in `config.yaml` and `GITHUB_ACCESS_TOKEN` must be set in `.env`. Use Marketplace → Install on the GitHub application module, or uncomment the block in `config.yaml`, then restart the API. Gatekeeper does not auto-enable integrations.

Sensitive tools (require session grant on `github.repo`):

- `github_list_repository_secrets`
- `github_get_repository_secret`
- `github_create_or_update_repository_secret`
- `github_delete_repository_secret`
- `github_delete_organization_repository`

## Integration points

| Consumer | Hook |
|---|---|
| `Agent.call_tools` | Pre-invoke `evaluate_tool_call`; post-success `record_tool_observation` |
| `ChatService` export | `evaluate_conversation_export` before returning transcript |
| Process-wide accessor | `engine/context.py` → `get_default_gatekeeper_service()` |

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/gatekeeper/GatekeeperService_test.py -v
```

## Adding a new integration policy

1. Implement `IGatekeeperPolicy` under `policies/`.
2. Register it in `GatekeeperService.__init__(policies=[...])`.
3. Define sensitive tools, resource extraction, and required grant actions.
4. Add tests mirroring `GatekeeperService_test.py`.
