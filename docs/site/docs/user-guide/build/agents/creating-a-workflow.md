# Creating a Workflow

Workflows implement business logic. They sit at the top of the stack, orchestrating integrations and querying the knowledge graph to fulfill specific user intents. They are exposed as agent tools and as REST API endpoints.

A workflow lives in a module, and the module's kind decides what it is written on: in an [in-engine module](/user-guide/build/modules/creating-a-module#remote-or-in-engine) it is `naas_abi_core` code, mounted on the REST API; in a [remote module](/user-guide/build/sdk/build-a-remote-module) it is `naas_abi_sdk` code that other modules call over NATS. `abi new workflow` writes the right one for the module you run it in. This page describes the in-engine workflow; [the remote one](#in-a-remote-module) is at the end.

---

## Role in the stack

```bash
┌─────────────────┐
│    Workflows    │ ← Business logic. Query graph, call integrations, compose results.
├─────────────────┤
│    Pipelines    │ ← Data ingestion. Transform raw data into RDF.
├─────────────────┤
│  Integrations   │ ← External API communication. No business logic.
└─────────────────┘
```

A workflow:
- Implements a specific, named intent (e.g. "reward long-term customers").
- Can query the triple store directly with SPARQL.
- Can call integrations for write operations or real-time data.
- Returns a deterministic result for the same inputs.
- Is exposed as a LangChain tool (for agents) and as a FastAPI endpoint.

If your output is RDF, write a [pipeline](/user-guide/build/knowledge-graph/creating-a-pipeline) instead.

---

## Scaffold one

From the project root:

```bash
abi new workflow Customers src/my_module/workflows
```

It writes `CustomersWorkflow.py`: the name is converted to PascalCase and `Workflow` is appended. The file holds three classes: a configuration, the parameters, and the workflow.

---

## Workflow class

```python
# workflows/CustomersWorkflow.py
from dataclasses import dataclass
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool
from my_module import ABIModule
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from pydantic import Field


@dataclass
class CustomersWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for CustomersWorkflow."""


class CustomersWorkflowParameters(WorkflowParameters):
    entity_id: Annotated[
        str, Field(..., description="The ID of the entity to summarize")
    ]


class CustomersWorkflow(Workflow[CustomersWorkflowParameters]):
    """Summarize an entity from the knowledge graph."""

    __configuration: CustomersWorkflowConfiguration

    def __init__(self, configuration: CustomersWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        # Services come from the module, declared in its `dependencies`.
        self.__triple_store = ABIModule.get_instance().engine.services.triple_store

    def run(self, parameters: CustomersWorkflowParameters) -> dict | list[dict]:
        sparql = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?label WHERE {{
                <http://ontology.naas.ai/abi/item/{parameters.entity_id}> rdfs:label ?label .
            }}
        """
        results = self.__triple_store.query(sparql)
        return {"entity_id": parameters.entity_id, "labels": [str(row[0]) for row in results]}

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="summarize_entity",
                description=(
                    "Summarize an entity from the knowledge graph. "
                    "Use when asked for information about an entity."
                ),
                func=lambda **kwargs: self.run(CustomersWorkflowParameters(**kwargs)),
                args_schema=CustomersWorkflowParameters,
            )
        ]
```

How the engine uses it:

- **Discovery.** The engine finds every `Workflow` subclass under `workflows/` and instantiates it with `New()` if the class defines one, else with an empty `<Name>WorkflowConfiguration()`. A workflow whose configuration needs arguments the engine cannot supply is skipped and logged, which is why the example reads its services from the module in `__init__` instead of taking them in the configuration.
- **Tools.** An agent gets the tools with `CustomersWorkflow(CustomersWorkflowConfiguration()).as_tools()`: see [Creating an Agent](/user-guide/build/agents/creating-an-agent).
- **REST.** `as_api` is inherited from `Expose`: when `run(parameters)` is a real override whose parameter is a Pydantic model, the API mounts `POST /workflows/<class name in snake case>` (here `POST /workflows/customers_workflow`) with the same bearer authentication as the agents. Override `as_api(router, ...)` only for a custom HTTP surface. A `run` that is only `pass` is not published. See the [REST API](/user-guide/build/applications/api).

---

## SPARQL as deterministic tools

For read-only workflows that are just structured queries, you do not need Python. Declare the query in the module's ontology folder and the `templatablesparqlquery` module turns it into an agent tool at startup. The scaffolded module already holds an example in `ontologies/queries/`:

```turtle
intentMapping:findRecordByIdQuery a intentMapping:TemplatableSparqlQuery ;
    rdfs:label "find_record_by_id"@en ;
    intentMapping:intentDescription "Look up a single record by its identifier." ;
    intentMapping:sparqlTemplate """
        SELECT ?record ?recordId WHERE { ... FILTER(STR(?recordId) = "{{ record_id }}") }
    """ ;
    intentMapping:hasArgument intentMapping:recordIdArg .
```

See [SPARQL Query Template System](/user-guide/build/knowledge-graph/sparql_query_template_system).

---

## Composing workflows

Workflows can compose other workflows for complex operations:

```python
class RewardCustomersWorkflow(Workflow[RewardCustomersParameters]):
    def __init__(self, configuration: RewardCustomersWorkflowConfiguration):
        super().__init__(configuration)
        self.__find_customers = FindCustomersWorkflow(FindCustomersWorkflowConfiguration())
        self.__credits_workflow = AddCreditsWorkflow(AddCreditsWorkflowConfiguration())

    def run(self, parameters: RewardCustomersParameters) -> dict:
        # Step 1: find eligible customers
        customers = self.__find_customers.run(
            FindCustomersParameters(min_months=parameters.min_months)
        )
        rewarded = []
        for customer in customers:
            # Step 2: add credits
            self.__credits_workflow.run(AddCreditsParameters(
                customer_id=customer["id"],
                credits=parameters.credits,
            ))
            rewarded.append(customer["id"])

        return {"rewarded": len(rewarded), "customer_ids": rewarded}
```

---

## Running a workflow on a schedule

A workflow is plain Python, so a [module job](/user-guide/build/modules/module-jobs) can call it: declare a `@job` on the module's `ABIModule` with a `Cron` or `Every` trigger and run the workflow in its handler.

```python
from datetime import timedelta
from naas_abi_core.module.jobs import Every, JobContext, job

class ABIModule(BaseModule):
    @job(triggers=(Every("1h"),), timeout=timedelta(minutes=10))
    def refresh_customers(self, ctx: JobContext) -> dict:
        from my_module.workflows.CustomersWorkflow import (
            CustomersWorkflow, CustomersWorkflowConfiguration, CustomersWorkflowParameters,
        )
        workflow = CustomersWorkflow(CustomersWorkflowConfiguration())
        return workflow.run(CustomersWorkflowParameters(entity_id="42"))  # stored on the run record
```

:::warning Legacy: Dagster
Dagster jobs (`abi new orchestration`) are the [legacy](/user-guide/build/applications/dagster) way to schedule a workflow in a project without NATS. They are removed in the next major.
:::

---

## In a remote module

`abi new workflow digest workflows`, run in a remote module's folder, writes the same three classes on `naas_abi_sdk` (no `naas_abi_core` import) and a test beside them. `run` is async, and the workflow is found, built and published by the module:

```python
# src/research/workflows/DigestWorkflow.py
from dataclasses import dataclass
from typing import Any

from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters
from pydantic import Field


@dataclass
class DigestWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for DigestWorkflow."""


class DigestWorkflowParameters(WorkflowParameters):
    message: str = Field(default="hello", description="Text the workflow echoes back")


class DigestWorkflow(Workflow[DigestWorkflowParameters]):
    """Echoes a message: this text is the description an agent or a caller reads."""

    async def run(self, parameters: DigestWorkflowParameters) -> dict[str, Any]:
        return {"message": parameters.message}
```

- **Discovery.** The module imports every `Workflow` under `workflows/`, builds it after `on_initialized` (with `New(module)` if the class defines it, else an empty configuration) and lists it in its descriptor by its class name in snake case: `digest_workflow`. Read what you need from the engine in `New(module)`: `await module.engine.services.secret.get("KEY")`. A workflow that cannot be built stops the module at start, naming it.
- **Tools.** In `on_initialized`, `await self.build_processes()` then `self.get_workflow("digest_workflow").as_tools()` gives the agent you create its tools.
- **Other modules.** `await engine.modules["my_project.research"].get_workflow("digest_workflow").run({"message": "hi"})` runs it over NATS: a request with a deadline (300 seconds by default), authorized through discovery before it runs, never retried. `as_tools()` on the awaited proxy gives a caller's agent the same tool. The kernel REST API does not mount remote workflows: for `POST /workflows/<slug>`, use an in-engine module.
- **Jobs.** Declare `job = JobSettings(triggers=(Every("1h"),))` on the class (`JobSettings()` alone: manual runs only) and the module hosts a job `workflow.digest_workflow`, with run records and the System app's list; `proxy.trigger({...})` starts a run from another module. A scheduled trigger needs parameters that all have defaults.
- **Test it** without a broker: `asyncio.run(workflow.run(DigestWorkflowParameters(message="hi")))` in `DigestWorkflow_test.py`.

The full walk-through, with the pipeline and the integration: [Build a Remote Module](/user-guide/build/sdk/build-a-remote-module#5-add-a-workflow-a-pipeline-or-an-integration).

---

## Best practices

- **One intent per workflow**: `GetCustomersByRevenue`, `SendOnboardingEmail`, `UpdateCompanyProfile` - each focused, each composable.
- **Validate parameters**: Pydantic validation is free; use `Field(description=...)` so agents know how to call the tool correctly.
- **Return structured data**: return dicts or Pydantic models. Agents and API consumers both benefit.
- **Log with context**: use `from naas_abi_core import logger` and `logger.info(...)`, not `print()`.
- **Test `run()` directly**: build the workflow and call `run(...)` with a parameters instance, in `<Name>Workflow_test.py` next to the file.
