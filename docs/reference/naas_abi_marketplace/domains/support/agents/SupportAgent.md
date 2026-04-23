# SupportAgent

## What it is
A support-focused `IntentAgent` factory that configures an agent to gather user feedback and create GitHub support tickets (bug reports or feature requests) using GitHub integrations and domain workflows.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `SupportAgent`.
  - Loads support-domain configuration (GitHub project ID and default repository).
  - Pulls GitHub access token from the GitHub application module.
  - Wires tools from GitHub REST + GraphQL integrations plus workflow tools for:
    - reporting bugs (`report_bug`)
    - feature requests (`feature_request`)
  - Registers intent triggers mapping common user phrases to the above tools.
  - Produces an `AgentConfiguration` with a system prompt that includes tool descriptions and repository/project placeholders filled.

- `class SupportAgent(IntentAgent)`
  - Concrete agent type returned by `create_agent`.
  - No additional behavior beyond `IntentAgent` (empty subclass).

## Configuration/Dependencies
- Support domain module configuration (via `naas_abi_marketplace.domains.support.ABIModule.get_instance().configuration`):
  - `github_project_id`
  - `default_repository`
- GitHub application module configuration (via `naas_abi_marketplace.applications.github.ABIModule.get_instance().configuration`):
  - `github_access_token`
- Model provider:
  - `naas_abi_marketplace.domains.support.models.default.get_model()`
- Tools are sourced and filtered from:
  - `naas_abi_marketplace.applications.github.integrations.GitHubIntegration.as_tools()`
    - Keeps: `github_list_repository_contributors`, `github_list_organization_repositories`
  - `naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration.as_tools()`
    - Keeps: `githubgraphql_list_priorities`, `githubgraphql_get_project_node_id`
  - Workflow toolsets:
    - `ReportBugWorkflow(...).as_tools()`
    - `FeatureRequestWorkflow(...).as_tools()`

## Usage
```python
from naas_abi_marketplace.domains.support.agents.SupportAgent import create_agent

agent = create_agent()

# Then use the returned IntentAgent with your runtime/orchestrator.
# (Exact invocation depends on the naas_abi_core agent runner used in your project.)
```

## Caveats
- `create_agent()` depends on `ABIModule` singletons being configured/initializable; missing configuration (GitHub token, project id, default repo) will prevent proper setup.
- The `SupportAgent` class itself adds no behavior; all logic is in `IntentAgent` and the configured tools/workflows.
