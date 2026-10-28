# pipelines — AGENTS.md

Pipelines of this remote module, written like in-engine ones but on
`naas_abi_sdk` only (`from naas_abi_sdk.pipeline import Pipeline, ...`; never
`naas_abi_core`). Create one with `abi new pipeline <Name> pipelines` from the
module folder.

- A pipeline is a `Pipeline[<Name>PipelineParameters]` with
  `async def run(self, parameters) -> Graph` (an rdflib graph). Parameters are a
  pydantic model (`PipelineParameters`). Write the graph to the engine yourself,
  for instance with `self.engine.services.triple_store.insert(graph, graph_name)`
  (declare `triple_store` in `ModuleDependencies`).
- `ABIModule` finds every `Pipeline` subclass defined under this folder
  (recursively; `*_test.py`, `test_*.py` and classes only imported are left out).
  Its name is the class name in snake case, unique in the module.
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
- Each one is also a one-step durable workflow, `pipeline.<name>`, started by
  name like a workflow's (see `../workflows/AGENTS.md`); its output is
  `{"format": "text/turtle", "triples": n, "data": "<turtle>"}`.
- Needs `naas-abi-sdk[workflows,rdf]`.
- Tests sit beside the code, `<Name>Pipeline_test.py`, and run offline.
