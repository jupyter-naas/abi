# pipelines — AGENTS.md

Pipelines of this remote module, written like in-engine ones but on
`naas_abi_sdk` only (`from naas_abi_sdk.pipeline import Pipeline, ...`; never
`naas_abi_core`). Create one with `abi new pipeline <Name> pipelines` from the
module folder.

- A pipeline is a `Pipeline[<Name>PipelineParameters]` with
  `async def run(self, parameters) -> Graph` (an rdflib graph). Parameters are a
  pydantic model (`PipelineParameters`). Write the graph to the engine yourself,
  for instance with `await module.engine.services.triple_store.insert(graph, graph_name)`
  from `run`, with the module the class got in `New(module)` (declare
  `triple_store` in `ModuleDependencies`). Callers of the durable workflow get
  the graph back only up to 60 KiB, so store it in `run`, not in the caller.
- `ABIModule` finds every `Pipeline` subclass defined under this folder
  (recursively; `*_test.py`, `test_*.py`, `tests/`, abstract classes and classes
  only imported are left out), or the ones listed in `pipelines = (...)` on the
  module class. Its name is the class name in snake case: `LoadItemsPipeline` is
  `load_items_pipeline`, unique in the module.
- After `on_initialized` it builds each one with `New(module)` (sync or async,
  a classmethod) if the class defines it, else with an empty
  `<Name>PipelineConfiguration`. A class that needs arguments and has neither is
  bound in `on_initialized` with `self.expose_pipeline(name, instance)`;
  otherwise the module does not start.
- Read credentials with `await module.engine.services.secret.get("KEY")`
  (declare `secret` in `ModuleDependencies`), never from the environment.
- Use them from the module: `self.get_pipeline_instance(name)` and `.as_tools()` for an
  agent (the graph is returned as turtle). An agent takes its tools when it is
  built, in `on_initialized`, where the pipelines are not built yet:
  `await self.build_processes()` first (idempotent; `expose_pipeline` the classes
  that need arguments before it), then pass the tools to
  `create_agent(..., tools=tools)`.
- Each one is also a one-step durable workflow, `pipeline.<name>`, that other
  modules, Nexus (System → Jobs) and scripts start by name
  (`await engine.modules[id].get_workflow("pipeline.<name>")`), its parameters
  model as the input schema. It needs the `document` service. Its output is
  `{"format": "text/turtle", "triples": n, "data": "<turtle>"}`, with `data`
  replaced by a `note` above 60 KiB. An input that does not fit the parameters
  fails the run without a retry.
- `job = JobSettings(triggers=(...), timeout=..., max_attempts=...,
  max_concurrency=...)` (`naas_abi_sdk.jobs`) on the class schedules it. The
  defaults are no trigger, one attempt and one run at a time: keep
  `max_attempts=1` unless `run` is safe to repeat, since a retry runs it again
  from the start and would insert twice. A `Cron` or `Every` trigger's `input`
  is the run's parameters and must fit them, or the module does not start; an
  `OnEvent` run takes the event's `data`. The name `pipeline.<name>` must not
  also be a `@job` or `@workflow` of the module.
- Needs `naas-abi-sdk[workflows,rdf]`.
- Tests sit beside the code, `<Name>Pipeline_test.py`, and run offline.
