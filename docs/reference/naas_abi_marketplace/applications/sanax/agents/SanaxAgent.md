# SanaxAgent

## What it is
An `IntentAgent` specialization configured to extract and analyze LinkedIn Sales Navigator data using a set of templated SPARQL query tools plus a utility tool (`count_items`) to count results returned by another tool.

## Public API
- `class SanaxAgent(IntentAgent)`
  - Agent metadata:
    - `name = "Sanax"`
    - `description = "Sanax agent to extract sales navigator data from LinkedIn."`
    - `avatar_url = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"`
    - `suggestions = []`
    - `system_prompt`: contains operating guidelines and a `[TOOLS]` placeholder expanded at runtime.

- `SanaxAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> SanaxAgent`
  - Creates and returns a configured `SanaxAgent` instance with:
    - Default chat model from the application model registry.
    - Tools:
      - `count_items` (a `StructuredTool`) to call another tool and count its returned items.
      - A predefined list of templated SPARQL query tools loaded by name.
    - Intents mapping common user phrases to tool targets.
    - Default `AgentSharedState(thread_id="0")` and default `AgentConfiguration(system_prompt=...)` when not provided.
    - No sub-agents (`agents = []`) and no memory (`memory=None`).

## Configuration/Dependencies
- **Core agent types**
  - `naas_abi_core.services.agent.IntentAgent`: `IntentAgent`, `Intent`, `IntentType`, `AgentSharedState`, `AgentConfiguration`
- **Model**
  - `naas_abi_marketplace.applications.sanax.ABIModule.get_instance().engine.services.model_registry.get_default_chat_model()`
- **Tools**
  - `naas_abi_core.modules.templatablesparqlquery.ABIModule.get_instance().get_tools(names)`
    - Loaded tool names:
      - Person: `sanax_get_persons_by_name_prefix`, `sanax_search_persons_by_name`, `sanax_list_persons`, `sanax_get_information_about_person`
      - Company: `sanax_search_companies_by_name`, `sanax_list_companies`, `sanax_get_company_employees`
      - Position: `sanax_get_people_holding_position`
      - Location: `sanax_search_locations_by_name`, `sanax_list_locations`, `sanax_get_people_located_in_location`
      - Timeline: `sanax_get_people_with_most_recent_job_starts`, `sanax_get_people_with_oldest_job_starts`, `sanax_get_people_with_longest_tenure`
  - `langchain_core.tools.StructuredTool` for the `count_items` tool
  - `pydantic.BaseModel` schema for `count_items` args
- **Logging**
  - `naas_abi_core.logger` used inside `count_items`

## Usage
```python
from naas_abi_marketplace.applications.sanax.agents.SanaxAgent import SanaxAgent

agent = SanaxAgent.New()

print(agent.name)                 # "Sanax"
print([t.name for t in agent.tools][:3])  # includes "count_items" + SPARQL tools
```

## Caveats
- Some intents target tool names that are **not** included in the loaded `templates_tools` list:
  - `sanax_count_people_working_for_company`
  - `sanax_count_people_located_in_location`
  If these tools are not available from the templated SPARQL module via other means, those intents will not be directly actionable.
- `count_items` returns `0` when:
  - The requested `function_name` is not found in the loaded tools, or
  - An exception occurs during invocation/counting.
