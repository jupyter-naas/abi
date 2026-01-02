from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
    MemorySaver,
)

NAME = "Pennylane"
DESCRIPTION = "A Pennylane Agent for managing accounting and financial operations."
MODEL = "o3-mini"
TEMPERATURE = 1
AVATAR_URL = "https://logo.clearbit.com/pennylane.tech"
SYSTEM_PROMPT = """Tu es un agent Pennylane avec accès aux outils d'intégration Pennylane.
Si tu n'as pas accès aux outils, demande à l'utilisateur de configurer son PENNYLANE_API_TOKEN dans le fichier .env.
Sois toujours clair et professionnel dans ta communication en aidant les utilisateurs à gérer leurs données comptables.
Fournis toujours tout le contexte (réponse des outils, brouillon, etc.) à l'utilisateur dans ta réponse finale.
"""


def create_agent(
    agent_shared_state: AgentSharedState | None = None,
    agent_configuration: AgentConfiguration | None = None,
):
    # Init
    tools: list = []
    agents: list = []

    # Set model
    from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini import model

    # Add integration based on available credentials
    from naas_abi_marketplace.applications.pennylane import ABIModule
    from naas_abi_marketplace.applications.pennylane.integrations.PennylaneIntegration import (
        PennylaneIntegrationConfiguration,
        as_tools,
    )

    module = ABIModule.get_instance()
    pennylane_api_token = module.configuration.pennylane_api_token
    integration_config = PennylaneIntegrationConfiguration(api_key=pennylane_api_token)
    tools += as_tools(integration_config)

    # Set configuration
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState(thread_id="0")

    return PennylaneAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        agents=agents,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=MemorySaver(),
    )


class PennylaneAgent(Agent):
    pass
