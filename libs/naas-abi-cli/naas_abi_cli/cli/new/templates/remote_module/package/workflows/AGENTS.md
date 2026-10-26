# workflows — AGENTS.md

Workflows of this remote module, written like in-engine ones but on
`naas_abi_sdk` only (`from naas_abi_sdk.workflow import Workflow, ...`; never
`naas_abi_core`). Create one with `abi new workflow <Name> workflows` from the
module folder.

- A workflow is a `Workflow[<Name>WorkflowParameters]` with
  `async def run(self, parameters)`. Parameters are a pydantic model
  (`WorkflowParameters`). Return a JSON-serializable value or a pydantic model.
- `ABIModule` finds every `Workflow` subclass defined under this folder
  (recursively; `*_test.py`, `test_*.py` and classes only imported are left out).
  Its name is the class name in snake case: `SendReportWorkflow` is
  `send_report_workflow`, unique in the module.
- After `on_initialized` it builds each one with `New(module)` (sync or async,
  a classmethod) if the class defines it, else with an empty
  `<Name>WorkflowConfiguration`. A class that needs arguments and has neither is
  bound in `on_initialized` with `self.expose_workflow(name, instance)`;
  otherwise the module does not start.
- Read credentials with `await module.engine.services.secret.get("KEY")`
  (declare `secret` in `ModuleDependencies`), never from the environment.
- Use them from the module: `self.get_workflow_instance(name)` and
  `.as_tools()` for an agent (LangChain, extra `[agents]` or `[agent]`). An agent
  takes its tools when it is built, in `on_initialized`, where the workflows are
  not built yet: `await self.build_processes()` first (idempotent; `expose_workflow`
  the classes that need arguments before it), then pass the tools to
  `create_agent(..., tools=tools)`.
- Each one is also a one-step durable workflow, `workflow.<name>`, that other
  modules, Nexus (System → Jobs) and scripts start by name
  (`await engine.modules[id].get_workflow("workflow.<name>")`), its parameters
  model as the input schema. It needs the `document` service. `job =
  JobSettings(triggers=(...), max_attempts=..., ...)` on the class schedules it;
  a `Cron` or `Every` trigger's `input` must fit the parameters, or the module
  does not start.
- Needs `naas-abi-sdk[workflows]`.
- Tests sit beside the code, `<Name>Workflow_test.py`, and run offline.
