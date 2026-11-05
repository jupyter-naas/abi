# naas-abi-marketplace-modules — AGENTS.md

Remote (SDK) versions of `naas_abi_marketplace.applications.*`. Tracking issue:
jupyter-naas/abi#1423.

## Rules

- **SDK only.** Never import `naas_abi_core`, `naas_abi` or
  `naas_abi_marketplace`. Each module's `tests/module_test.py` checks it in a
  fresh interpreter, and the Dockerfile fails if one is installed.
- One application = one subpackage `naas_abi_apps/<app>/` = one remote module =
  one process (`python -m naas_abi_apps.<app>`). `naas_abi_apps` is a namespace
  package: no `__init__.py` at its root.
- `MODULE_ID = "applications.<app>"`. Never change it: discovery and agent
  memory are keyed by it.
- Shared runtime (READY wait, signals, environment) is in
  `naas_abi_apps/common/runtime.py`. `__main__.py` is three lines on top of it.
- Configuration: a `ModuleConfiguration` dataclass of plain settings, set from
  `<APP>_<FIELD>` variables. **Credentials are engine secrets**, read in
  `on_initialized` with `await self.engine.services.secret.get(name)`; the
  configuration holds the secret's *name* (`api_key_secret`).
- Declare every engine service used in `ModuleDependencies(services=...)`.
- Agents: `naas_abi_sdk.agents.Agent` / `IntentAgent`, models from
  `model_registry`, memory from `document_memory(...)`, published in
  `ABIModule.agents` and bound with `expose_agent` in `on_initialized`. Keep
  the in-engine agent's name, prompt and tool names.
- Integrations: `naas_abi_sdk.integration`, **async** (`httpx`), with an
  optional `transport` for tests and an optional object `storage` for the
  archived JSON the in-engine version wrote with `StorageUtils`. Tools use
  `StructuredTool(coroutine=...)`.
- Workflows / pipelines: `naas_abi_sdk.workflow` / `.pipeline` under
  `workflows/` / `pipelines/`. Dagster orchestrations become `@job` /
  `@workflow` methods. Ontologies are `.ttl` files under `ontologies/`.
- Third-party dependencies go in the application's extra in `pyproject.toml`.
- Tests are offline (`httpx.MockTransport`, fakes for engine services).

## Port checklist (per application)

1. `naas_abi_apps/<app>/`: `__init__.py` (`ABIModule`), `__main__.py`,
   `agents/`, `integrations/`, `tests/module_test.py`, tests beside the code.
2. Extra `<app>` in `pyproject.toml`; row in `README.md`.
3. Mark the in-engine module deprecated (docstring pointing here). It is
   removed in the cleanup phase of #1423, not in the port.

## Decision (2026-11-05): layout of the remote application modules

**Context.** A remote module must not import `naas_abi_core`, and
`naas-abi-marketplace` depends on it, so the ports cannot live in that
distribution. The SDK runs one `ABIModule` per process.

**Decision.** One new distribution, `naas-abi-marketplace-modules`, holding one
subpackage per application under the `naas_abi_apps` namespace, with one extra
per application and one Dockerfile parametrized by `APP`. Module ids are
`applications.<app>`. Secrets come from the engine's `secret` service.

**Consequences.**
- One lockfile, one test run and one CI job for all ports, instead of 48
  repositories; each image still installs only its application's extra.
- Each application is still its own process, deployable and restartable alone.
- In-engine consumers of an application (`support` → github, `ontology_engineer`
  → naas, `organizations` → sec_gov, ...) must call it over NATS
  (`get_agent`, durable workflows) once its in-engine module is removed.
- The placeholder agents (no tools) are not ported one by one: see #1423.
