# Agent Composer Service — AGENTS.md

> Scope: `libs/naas-abi-core/naas_abi_core/services/agent_composer/`. Canonical reference for agents.

## Purpose

Build runnable agents without an agent Python file: from a stored **record**
(`AgentSpec`) or from Python values (`create`). Tools come from the tool
registry (`services/tool_registry`), models from the model registry. The
result is a regular `Agent`, or a `CapabilityAgent` when the record enables
runtime discovery. Decision record:
`docs/adr/20260923_tool-registry-and-agent-composition.md`.

## Files

```
agent_composer/
├── AgentComposerPort.py        # AgentSpec record schema, ports, exceptions
├── AgentComposerService.py     # compose() / create() / load()
├── AgentComposerFactory.py     # InMemory(...), FileSystem(...), FromEngine(...)
├── adapters/secondary/
│   ├── InMemoryAgentSpecRepositoryAdapter.py
│   ├── FileSystemAgentSpecRepositoryAdapter.py   # <dir>/<name>.yaml|.yml|.json
│   ├── SecretServiceResolverAdapter.py           # engine Secret service
│   └── MappingSecretResolverAdapter.py           # plain mapping
└── tests/
    ├── agent_spec_repository__secondary_adapter__generic_test.py
    ├── secret_resolver__secondary_adapter__generic_test.py
    └── AgentComposer_acceptance_test.py           # end-to-end scenarios
```

## Record (`AgentSpec`, `kind: abi.agent/v1`)

```yaml
kind: abi.agent/v1
name: triage                     # [A-Za-z0-9_-]{1,64}; also the file name
description: Files and routes bug reports.
prompt: |
  You triage bug reports.
model: gpt-4.1-mini              # or {id, provider}; omit = default chat model
tools:
  - naas_abi_marketplace.applications.github/github_create_issue   # short form
  - tool: acme.tracker/create_ticket@1
    config:
      api_token: {secret: TRACKER_TOKEN}                            # never the value
sub_agents:
  - researcher                   # another record's name
capabilities:                    # optional runtime discovery (CapabilityAgent)
  enabled: true
  allow: ["naas_abi_marketplace.applications.github/*"]
  max_enabled: 5
  tool_config:
    naas_abi_marketplace.applications.github/github_create_issue@1:
      access_token: {secret: GITHUB_TOKEN}
```

Config values are literals or `{secret: NAME}`. A value for a key the tool
declares `secret` must be a secret reference; an inline credential is a
composition error.

## Ports (`AgentComposerPort.py`)

```python
class IAgentSpecRepository: get(name), list(), save(spec), delete(name)   # AgentSpecNotFoundError
class ISecretResolverPort:  resolve(key) -> str | None
```

Exceptions: `AgentCompositionError` (`.problems`: every issue found at once),
`AgentSpecNotFoundError`, `AgentSpecInvalidError`, `SubAgentCycleError`
(`.cycle`), `ToolNameCollisionError`.

## Service API (`AgentComposerService.py`)

```python
AgentComposerService(tool_registry, model_registry, spec_repository=None, secret_resolver=None, memory_factory=None)

compose(spec_or_name, *, sub_agents=[Agent...], tools=[BaseTool...], context=ToolContext|None,
        state=AgentSharedState|None, memory=None, event_queue=None) -> Agent
create(*, name, prompt, description="", model=None, tools=[ref | ToolBindingSpec | BaseTool],
       sub_agents=[record name | Agent], capabilities=None, context=None, state=None, memory=None) -> Agent
load(name) -> AgentSpec
```

- `context` is the caller (user, workspace, scopes): it decides which
  registry tools may be bound.
- Sub-agents follow the runtime's supervisor pattern: one shared
  `AgentSharedState` whose `supervisor_agent` is the composed agent; record
  sub-agents are composed recursively, existing instances are `duplicate()`d
  onto that state (the caller's instance is not mutated).
- Validation reports all problems together (unknown/denied tools, missing
  config or secrets, inline credentials, unknown models or records), then
  checks cycles and model-facing name collisions (tools, default tools,
  `transfer_to_*` handoffs, capability tools, `request_help`).
- Each composition starts a fresh conversation (random thread id) unless a
  `state` is passed.

Programmatic example:

```python
composer = AgentComposerFactory.FromEngine(engine, records_directory="agents/")
calculator = CalculatorAgent.New()
lead = composer.create(
    name="lead",
    prompt="Delegate arithmetic to the calculator.",
    model="gpt-4.1-mini",
    tools=["naas_abi_marketplace.applications.github/github_list_issues"],
    sub_agents=[calculator, "researcher"],
)
lead.invoke("...")
```

## Factory (`AgentComposerFactory.py`)

```python
AgentComposerFactory.InMemory(tool_registry, model_registry, specs=(), secrets=None)
AgentComposerFactory.FileSystem(tool_registry, model_registry, directory, secret_resolver=None)
AgentComposerFactory.FromEngine(engine, spec_repository=None, records_directory=None, **options)  # after Engine.load()
```

## Tests

```bash
uv run pytest libs/naas-abi-core/naas_abi_core/services/agent_composer -o addopts=""
```

## Adding a new record repository

1. Implement every `IAgentSpecRepository` method in `adapters/secondary/<Name>AgentSpecRepositoryAdapter.py`; store the record's JSON (`spec.model_dump(mode="json")`) and validate on read.
2. Raise `AgentSpecNotFoundError` for missing names and `AgentSpecInvalidError` for records failing the schema.
3. Add `<Name>AgentSpecRepositoryAdapter_test.py` subclassing `AgentSpecRepositorySecondaryAdapterContract` with a `repository` fixture.
