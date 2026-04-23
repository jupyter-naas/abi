# SanaxAgent

## What it is
A thin wrapper around `naas_abi_core.services.agent.IntentAgent` that configures an intent-driven agent (“Sanax”) for extracting and analyzing LinkedIn Sales Navigator data via pre-defined SPARQL template tools plus a utility tool to count tool results.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `SanaxAgent` with:
    - System prompt (including a generated tool list).
    - A set of tools (templated SPARQL query tools + `count_items`).
    - A set of `Intent` patterns mapped to tool targets.
    - Default state (`thread_id="0"`) and default configuration if not provided.

- `class SanaxAgent(IntentAgent)`
  - No additional behavior; inherits all functionality from `IntentAgent`.

## Configuration/Dependencies
- **Core agent framework**
  - `naas_abi_core.services.agent.IntentAgent`: `IntentAgent`, `Intent`, `IntentType`, `AgentSharedState`, `AgentConfiguration`
- **Tools**
  - `naas_abi_core.modules.templatablesparqlquery.ABIModule.get_instance().get_tools(...)` to load named SPARQL template tools:
    - Person: `sanax_get_persons_by_name_prefix`, `sanax_search_persons_by_name`, `sanax_list_persons`, `sanax_get_information_about_person`
    - Company: `sanax_search_companies_by_name`, `sanax_list_companies`, `sanax_get_company_employees`
    - Position: `sanax_get_people_holding_position`
    - Location: `sanax_search_locations_by_name`, `sanax_list_locations`, `sanax_get_people_located_in_location`
    - Timeline: `sanax_get_people_with_most_recent_job_starts`, `sanax_get_people_with_oldest_job_starts`, `sanax_get_people_with_longest_tenure`
  - `langchain_core.tools.StructuredTool` used to expose `count_items` as a tool with `pydantic` args schema.
- **Model**
  - `naas_abi_marketplace.applications.sanax.models.default.model` used as `chat_model`.
- **Logging**
  - `naas_abi_core.logger` used inside `count_items`.

## Usage
```python
from naas_abi_marketplace.applications.sanax.agents.SanaxAgent import create_agent

agent = create_agent()

# The returned object is an IntentAgent (SanaxAgent subclass) configured with tools and intents.
print(agent.name)         # "Sanax"
print(len(agent.tools))   # includes "count_items" plus SPARQL template tools
```

## Caveats
- Some intents reference tool targets that are **not** added to the tool list in this module:
  - `sanax_count_people_working_for_company`
  - `sanax_count_people_located_in_location`
  If those tools are not provided elsewhere by the templatable SPARQL module, these intents may not be actionable.
- `count_items` returns `0` if the requested tool name is not found or if an exception occurs during tool invocation.
