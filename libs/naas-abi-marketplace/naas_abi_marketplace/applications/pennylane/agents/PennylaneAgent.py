from __future__ import annotations

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)


class PennylaneAgent(Agent):
    name: str = "Pennylane"
    description: str = "A Pennylane Agent for managing accounting and financial operations."
    avatar_url: str = "https://www.pennylane.tech/favicon.ico"
    system_prompt: str = """Tu es un agent Pennylane avec accès aux outils d'intégration Pennylane.
Si tu n'as pas accès aux outils, demande à l'utilisateur de configurer son PENNYLANE_API_TOKEN dans le fichier .env.
Sois toujours clair et professionnel dans ta communication en aidant les utilisateurs à gérer leurs données comptables.
Fournis toujours tout le contexte (réponse des outils, brouillon, etc.) à l'utilisateur dans ta réponse finale.
"""

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
    ) -> PennylaneAgent:

        from naas_abi_marketplace.applications.pennylane import ABIModule
        from naas_abi_marketplace.applications.pennylane.integrations.PennylaneIntegration import (
            PennylaneIntegrationConfiguration,
            as_tools,
        )



        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        module = ABIModule.get_instance()
        pennylane_api_token = module.configuration.pennylane_api_token
        integration_config = PennylaneIntegrationConfiguration(api_key=pennylane_api_token)

        tools: list = []
        tools += as_tools(integration_config)

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=[],
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=MemorySaver(),
        )
