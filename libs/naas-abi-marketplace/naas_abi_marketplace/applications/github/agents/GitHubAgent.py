from __future__ import annotations

from typing import Optional

from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    IntentAgent,
)


class GitHubAgent(IntentAgent):
    name: str = "GitHub"
    description: str = (
        "Helps you interact with GitHub through its REST API and GraphQL API."
    )
    avatar_url: str = (
        "https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png"
    )
    system_prompt: str = """<role>
You are a GitHub Agent with expertise in repository management, issue tracking, project management, and collaboration workflows.
</role>

<objective>
Help users effectively manage their GitHub repositories, issues, pull requests, projects, and collaboration workflows.
</objective>

<context>
You have access to GitHub tools for GitHub operations.
</context>

<tasks>
- Analyze user requests and identify required GitHub operations
- Validate input parameters before executing any tool
- Execute GitHub operations using appropriate tools
- Provide clear, informative responses about completed actions
</tasks>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Validate that all required parameters are provided and valid before using tool.
- Use descriptive titles and detailed descriptions when creating issues or pull requests
- Provide clear, concise responses with relevant information from tool responses
</operating_guidelines>

<constraints>
- Only use the provided GitHub tools - do not make assumptions about external APIs
- Do not attempt operations beyond the scope of the available tools
</constraints>
"""

    suggestions: list = []

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "GitHubAgent":
        from naas_abi_core.engine.context import get_default_model_registry
        from naas_abi_marketplace.applications.github import ABIModule
        from naas_abi_marketplace.applications.github.agents.intents.GitHubAgentIntents import (
            INTENTS,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
            GitHubGraphqlIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
            as_tools as GitHubGraphqlIntegration_tools,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
            GitHubIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
            as_tools as GitHubIntegration_tools,
        )

        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()
        embedding_model = registry.get_default_embedding_model().model

        module = ABIModule.get_instance()
        github_access_token = module.configuration.github_access_token

        tools: list = []
        github_integration_config = GitHubIntegrationConfiguration(
            access_token=github_access_token
        )
        tools += GitHubIntegration_tools(github_integration_config)
        github_graphql_integration_config = GitHubGraphqlIntegrationConfiguration(
            access_token=github_access_token
        )
        tools += GitHubGraphqlIntegration_tools(github_graphql_integration_config)

        system_prompt = cls.system_prompt.replace(
            "[TOOLS]",
            "\n".join([f"- {tool.name}: {tool.description}" for tool in tools]),
        )
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            embedding_model=embedding_model,
            tools=tools,
            agents=[],
            intents=INTENTS,
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
