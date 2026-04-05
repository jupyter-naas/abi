# Creating a Workflow

Workflows implement business logic. They sit at the top of the stack, orchestrating integrations and querying the knowledge graph to fulfill specific user intents. They are exposed as agent tools and as REST API endpoints.

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

---

## Workflow class

```python
# workflows/MyWorkflow.py
from naas_abi_core.workflow.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi.modules.custom.my_module.integrations.MyIntegration import (
    MyIntegration, MyIntegrationConfiguration,
)
from dataclasses import dataclass
from pydantic import BaseModel, Field
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from typing import Any

@dataclass
class MyWorkflowConfiguration(WorkflowConfiguration):
    triple_store_service: TripleStoreService
    integration_config: MyIntegrationConfiguration

class MyWorkflowParameters(WorkflowParameters):
    entity_id: str = Field(..., description="The ID of the entity to process")
    action: str = Field(..., description="Action to perform: 'summarize' or 'update'")

class MyWorkflow(Workflow):
    __configuration: MyWorkflowConfiguration

    def __init__(self, configuration: MyWorkflowConfiguration):
        self.__configuration = configuration
        self.__integration = MyIntegration(configuration.integration_config)

    def run(self, parameters: MyWorkflowParameters) -> Any:
        if parameters.action == "summarize":
            return self._summarize(parameters.entity_id)
        elif parameters.action == "update":
            return self._update(parameters.entity_id)
        else:
            raise ValueError(f"Unknown action: {parameters.action}")

    def _summarize(self, entity_id: str) -> dict:
        # Query the knowledge graph
        sparql = f"""
            PREFIX abi: <http://ontology.naas.ai/abi/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

            SELECT ?label ?url WHERE {{
                <http://ontology.naas.ai/abi/item/{entity_id}> rdfs:label ?label .
                OPTIONAL {{ <http://ontology.naas.ai/abi/item/{entity_id}> abi:url ?url }}
            }}
        """
        results = self.__configuration.triple_store_service.query(sparql)
        return {"entity_id": entity_id, "data": list(results)}

    def _update(self, entity_id: str) -> dict:
        # Fetch fresh data from external service and store
        item = self.__integration.get_item(entity_id)
        return {"updated": True, "item": item}

    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="my_workflow",
                description=(
                    "Process an entity: summarize its knowledge graph data or update it "
                    "from the external service. Use when asked to get info about or refresh an entity."
                ),
                func=lambda **kwargs: self.run(MyWorkflowParameters(**kwargs)),
                args_schema=MyWorkflowParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        @router.post("/workflows/my-workflow")
        def run_workflow(parameters: MyWorkflowParameters):
            return self.run(parameters)
```

---

## SPARQL as deterministic tools

For read-only workflows that are just structured queries, use the `TemplatableSparqlQuery` module instead of writing Python. Create a `.sparql` template file:

```sparql
# workflows/queries/get_entity.sparql
PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?label ?url WHERE {
    <http://ontology.naas.ai/abi/item/{{ entity_id }}> rdfs:label ?label .
    OPTIONAL { <http://ontology.naas.ai/abi/item/{{ entity_id }}> abi:url ?url }
}
```

See [[libs/naas-abi-core/Built-in-Module-Templatable-SPARQL|Templatable SPARQL module]].

---

## Composing workflows

Workflows can compose other workflows for complex operations:

```python
class RewardCustomersWorkflow(Workflow):
    def run(self, parameters: RewardCustomersParameters) -> dict:
        # Step 1: find eligible customers
        customers = self.__find_customers.run(
            FindCustomersParameters(min_months=parameters.min_months)
        )
        results = []
        for customer in customers:
            # Step 2: add credits via integration
            self.__credits_workflow.run(AddCreditsParameters(
                customer_id=customer["id"],
                credits=parameters.credits,
            ))
            # Step 3: send email via integration
            self.__email_workflow.run(SendEmailParameters(
                customer_id=customer["id"],
                subject=parameters.email_subject,
                body=parameters.email_body,
            ))
            results.append(customer["id"])

        return {"rewarded": len(results), "customer_ids": results}
```

---

## Best practices

- **One intent per workflow**: `GetCustomersByRevenue`, `SendOnboardingEmail`, `UpdateCompanyProfile` - each focused, each composable.
- **Validate parameters**: Pydantic validation is free; use `Field(description=...)` so agents know how to call the tool correctly.
- **Return structured data**: return dicts or Pydantic models. Agents and API consumers both benefit.
- **Log with context**: use `abi.logger.info("action", entity_id=entity_id)` not `print()`.
