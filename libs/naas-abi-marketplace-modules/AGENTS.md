# naas-abi-marketplace-modules — AGENTS.md

Remote (SDK) versions of `naas_abi_marketplace.applications.*`. Tracking issue:
jupyter-naas/abi#1423.

## Rules

- **SDK only.** Never import `naas_abi_core`, `naas_abi` or
  `naas_abi_marketplace`. Each module's `tests/module_test.py` checks it in a
  fresh interpreter, and the Dockerfile fails if one is installed.
- **The image installs from the lock.** `requirements/<app>.txt` is the
  app's extra exported from `uv.lock` with hashes, and the Dockerfile installs
  only those (`--require-hashes`), then the local proto, SDK and this package
  with `--no-deps`. After changing an extra or the lock, regenerate them (from
  this folder, for each extra):
  `uv export --frozen --no-dev --no-emit-project --no-emit-package naas-abi-proto --no-emit-package naas-abi-sdk --extra <extra> --format requirements-txt -o requirements/<app>.txt`.
  `common/image_test.py` fails while one is out of step.
- One application = one subpackage `naas_abi_apps/<app>/` = one remote module =
  one process (`python -m naas_abi_apps.<app>`). `naas_abi_apps` is a namespace
  package: no `__init__.py` at its root.
- `MODULE_ID = "applications.<app>"`. Never change it: discovery and agent
  memory are keyed by it.
- Shared code is in `naas_abi_apps/common/`: `runtime` (READY wait, signals,
  configuration from the environment; `__main__.py` is three lines on top of
  it), `agents` (`build_agent`, `read_secrets`, `tools_prompt`), `http`
  (`HttpConfiguration`, `request`, `request_json` over httpx), `storage`
  (`archive_json`), `graph` (core-free `ABIGraph`, `rows`, `sparql_string`),
  `sparql_templates` (templatable SPARQL queries of `ontologies/*.ttl` as tools,
  instead of core's `templatablesparqlquery`) and `testing` (fake engine
  services, `FakeTripleStore` running real SPARQL, `no_core_import`).
- In-engine tools that are lambdas with positional parameters become
  `schema_tool(fn, Schema)` coroutines (arguments validated, defaults filled).
- User input in SPARQL goes through `sparql_string`, never an f-string.
- Configuration: a `ModuleConfiguration` dataclass of plain settings, set from
  `<APP>_<FIELD>` variables. **Credentials are engine secrets** under the
  module's id (`applications.<app>/<NAME>`: the engine refuses a module any
  other name), read in `on_initialized` with
  `common.agents.read_secrets(engine, names, module_id=MODULE_ID)`; the
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
- Blocking libraries (yfinance, ...) run in `asyncio.to_thread`, never on the
  module's event loop.
- A tool intent whose tool is absent (no credentials) is dropped. RAW intents
  that say "I have no access to tools" are not ported when the agent has tools.
- Tests are offline (`httpx.MockTransport`, fakes for engine services).
- A tool that fetches a URL the model or a user gives fetches it with
  `common.public_fetch.fetch_public` (public addresses only, every redirect
  checked, size and time capped), never with `common.http.request`, which is
  for the application's own API host.
- An agent on a credential the module holds for the whole deployment reads,
  and writes only through what its configuration names (GitHub
  `agent_write_tools` / `repositories`, SendGrid `allowed_senders`, PostgreSQL
  `read_only`). A tool that deletes what cannot be restored or reveals a
  secret value stays an integration method, not an agent tool.
- Request paths built from tool arguments are checked one segment at a time
  (`checked_endpoint` in the GitHub and Naas integrations); query values go
  in `params`.

## Port checklist (per application)

1. `naas_abi_apps/<app>/`: `__init__.py` (`ABIModule`), `__main__.py`,
   `agents/`, `integrations/`, `tests/module_test.py`, tests beside the code.
2. Extra `<app>` in `pyproject.toml`; row in `README.md`.
3. Remove the in-engine module, its extra, its `naas_abi` soft dependency and
   its `make chat-*` target. An in-engine module that needs its raw client gets
   its own copy (as `support` → GitHub, `people` → LinkedIn export below).

## Decision (2026-11-05): cleanup, no compatibility window

**Context.** Decision 6 of #1423: keep the ported in-engine modules
(deprecated) for a release, or remove them.

**Decision.** Removed with the ports, in the same PR: the in-engine versions of
the 17 applications above and `applications.openrouter`, their extras, their
`naas_abi` soft dependencies, their `make chat-*` targets and their generated
reference docs. Kept in-engine: `git`, `bodo`, `naas` (its ontology YAML
workflows and triggers; the agent is removed) and `x`, which was ported and
removed in a later PR (decision on `x` below).
In-engine code that used a removed client got its own copy:
- `support` owns `GitHubIntegration` and `GitHubGraphqlIntegration`
  (`domains/operations/modules/support/integrations/`; `pynacl` in the
  `domains-support` extra). It needs the raw REST and GraphQL calls (project
  fields, iterations), which the remote module exposes only through its agent;
- `people` owns the LinkedIn connections import (decision above);
- `organizations` dropped its unused `applications.sec_gov` soft dependency;
- `config.remote.yaml` loads `ai.openrouter` instead of `applications.openrouter`.

**Consequences.** A project that loads a removed module in `modules:` fails at
load: it removes the entry and runs the remote module (README), with the
credentials as engine secrets. The migration note is in
`naas_abi_marketplace/applications/AGENTS.md`.

## Decision (2026-11-05): linkedin and the people module

**Context.** The in-engine `linkedin` application imported the people domain
module (graph builders, privacy check, profile documents) for its
`ActOfConnectionsOnLinkedInExportPipeline`, which turns a member's
`Connections.csv` into acts of connection in the people graphs. A remote
module cannot import a domain module.

**Decision.** That pipeline is people work: it moved to
`domains/intelligence/modules/people/pipelines/`, with the LinkedIn ontology it
instantiates (`ontologies/modules/LinkedInOntology.*`, `ActOfConnectionProcess`,
the generated classes) and the CSV reader (`utils/linkedin_connections_csv.py`).
The remote `linkedin` module keeps what talks to LinkedIn (the Voyager API with
the member's cookies, the Google page searches of `google_search`) and what
reads the connections back: the query templates, rewritten for what the
pipeline writes (`abi:Person`, `linkedin:hasConnectionOwner` /
`hasConnectedPerson`; the in-engine ones queried `linkedin:involvesAgent`,
which nothing wrote), and the name embeddings for the KG agent, as a durable
workflow run once at start instead of at every engine load.

**Not ported.** `LinkedInExportIntegration` (ZIP export reader) and the
`LinkedInExportConnectionsPipeline` / `LinkedInExportProfilePipeline` (an older
graph model, no caller): the people pipeline replaces them.

## Decision (2026-11-05): powerpoint

The in-engine PowerPoint agent never ran (it read an undefined
`naas_api_key`; its template was not in the repository). The remote module ports
the integration, the slide-import pipeline and the create-from-template workflow,
with a plain agent using them as tools instead of the custom LangGraph. Its
default template is generated: `templates/make_template.py` writes
`TemplateMinimal.pptx` (title, content and two-column slides; each text shape's
alt text says what goes in it). `template_path` points at a real template in
object storage.

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
- In-engine consumers of an application call it over NATS (`get_agent`,
  durable workflows), or keep their own copy of a raw client (cleanup decision).
- The 27 placeholder agents (no tools) are not ported: they were removed from
  the marketplace (#1423).

## Decision (2026-11-17): x, synchronous bodies over a blocking bridge

**Context.** `x` (24k lines, #1425–#1428) hosted its durable flows on core's
in-engine workflow runtime (sync handlers, `SyncFlowContext`), skipped
overlapping ticks by reading the job host's run records, kept its dataset in
core's DuckLake service (namespace `x`, with engine-only catalog SQL), and its
`x_proxy` app was served by the engine's FastAPI. Most of its code (graph
mapping, dataset projection, app snapshots) is synchronous and CPU-bound, and
well tested.

**Decision.**
- The synchronous bodies are kept. They run in worker threads
  (`asyncio.to_thread`) and reach the engine through `x/services.py`
  `SyncModule`: the SDK services with their own method names, each call
  blocking until it finished on the module's loop (a call made on the loop
  itself raises). The workflow handlers, the agent's tools and
  `XIntegration` (httpx) are async.
- Overlapping ticks: the SDK's new `skip_if_running` (a run whose input equals
  an earlier active run's ends SKIPPED; first attempt only) replaces the guard
  that read the host's run records.
- Dataset: the SDK dataset service, in the module's own namespace. Only plain
  `SELECT`s pass a module's query check, so the catalog SQL is gone: tables
  are created from the current specs, compaction is `compact` and `flush` per
  table, snapshot expiry and file cleanup are the engine's `dataset_cleanup`
  job. The tables are rebuilt from the envelopes (`reprocess_tweet_envelopes`),
  which stay where they were in object storage.
- The Recent Tweets app is an ASGI app bound with `expose_app`
  (`remote/applications.x:x_proxy`). Its Python code is the package
  `x/x_proxy/`, outside the folder the app host serves (`apps/x_proxy/`, the
  manifest only).
- The Dagster orchestrations and the CLI scripts that booted an engine are
  retired: the workflows and jobs cover them (#1428).

**Consequences.** One process holds the agent, the flows and the app; heavy
work never blocks the loop that serves them. A deployment migrating from the
in-engine module runs one `reprocess_tweet_envelopes` to rebuild its dataset
(migration note in `naas_abi_marketplace/applications/AGENTS.md`).

## Not ported yet

- Of `naas`, only the agent and the integration are ported; its ontology YAML
  workflows (core's `OntologyYaml`) stay in-engine with `ontology_engineer`.

## Not ported (decided, #1423)

- `git` stays in-engine. Its agent runs `git`, `make` and `gh` in the working
  directory of the process, and `abi chat naas_abi_marketplace.applications.git
  GitAgent` loads it in the CLI process (`make commit`, `make pr` in projects).
  A remote module runs elsewhere (a container, another cwd).
- `openrouter` is left to `naas_abi_marketplace.ai.openrouter`, which serves
  the OpenRouter models through the engine's model registry with the same API
  integration. The per-model agents of `applications.openrouter` are not
  ported; the module was removed.
