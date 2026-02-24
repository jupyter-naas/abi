from typing import Optional

from naas_abi_core import logger
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration import (
    OpenRouterAPIIntegration,
)
from naas_abi_marketplace.applications.openrouter.models.OpenRouterModel import (
    OpenRouterModel,
)


class OpenRouterAgents:
    def __init__(
        self,
        openrouter_integration: OpenRouterAPIIntegration,
        openrouter_model: OpenRouterModel,
    ):
        self.openrouter_integration = openrouter_integration
        self.openrouter_model = openrouter_model

    def _create_model_agent_class(self, model_data: dict) -> type[Agent]:
        """Dynamically create an agent class for a given model."""
        model_id = model_data.get("id", "")
        model_name = model_data.get("name", model_id)
        model_description = model_data.get(
            "description", f"An agent using {model_name}"
        )

        # Create a safe class name from model_id
        # e.g., "anthropic/claude-sonnet-4.6" -> "AnthropicClaudeSonnet46Agent"
        class_name_parts = model_id.replace("/", " ").replace("-", " ").split()
        class_name = "".join(word.capitalize() for word in class_name_parts) + "Agent"

        # Create the agent class factory function
        def create_agent_factory(m_id: str, m_name: str, m_desc: str):
            def create_agent(
                cls,
                agent_shared_state: Optional[AgentSharedState] = None,
                agent_configuration: Optional[AgentConfiguration] = None,
            ) -> Agent:
                # Create ChatOpenRouter model instance
                chat_model = self.openrouter_model.get_model(m_id)

                # Use provided configuration or create default one
                if agent_configuration is None:
                    # Extract model capabilities and specifications
                    context_length = model_data.get("context_length", "unknown")
                    modality = model_data.get("architecture", {}).get(
                        "modality", "text->text"
                    )
                    input_modalities = ", ".join(
                        model_data.get("architecture", {}).get(
                            "input_modalities", ["text"]
                        )
                    )
                    output_modalities = ", ".join(
                        model_data.get("architecture", {}).get(
                            "output_modalities", ["text"]
                        )
                    )
                    tokenizer = model_data.get("architecture", {}).get(
                        "tokenizer", "unknown"
                    )

                    # Extract pricing information
                    pricing = model_data.get("pricing", {})
                    prompt_cost = pricing.get("prompt", "N/A")
                    completion_cost = pricing.get("completion", "N/A")

                    # Build comprehensive system prompt
                    system_prompt = f"""You are a helpful AI assistant powered by {m_name}.

Model Specifications:
- Model ID: {m_id}
- Context Window: {context_length:,} tokens
- Modality: {modality}
- Input Capabilities: {input_modalities}
- Output Capabilities: {output_modalities}
- Tokenizer: {tokenizer}

Pricing (per token):
- Prompt: ${prompt_cost}
- Completion: ${completion_cost}

Description: {m_desc}

You excel at providing accurate, helpful, and contextually appropriate responses. Leverage your capabilities to assist users effectively while being mindful of token usage and context limits."""

                    agent_configuration = AgentConfiguration(
                        system_prompt=system_prompt
                    )

                # Use provided shared state or create new one
                if agent_shared_state is None:
                    agent_shared_state = AgentSharedState()

                tools: list = []
                agents: list = []

                return cls(
                    name=m_name,
                    description=m_desc,
                    chat_model=chat_model,
                    tools=tools,
                    agents=agents,
                    memory=None,
                    state=agent_shared_state,
                    configuration=agent_configuration,
                )

            return create_agent

        # Create the agent class dynamically
        create_agent_func = create_agent_factory(
            model_id, model_name, model_description
        )

        agent_cls = type(
            class_name,
            (Agent,),
            {
                "New": classmethod(create_agent_func),
            },
        )

        return agent_cls

    def create_agents(
        self, include_models: list[str] | None = None
    ) -> list[type[Agent]]:
        include_models = include_models or []
        agents: list[type[Agent]] = []
        # Load models and create agent classes
        try:
            models = self.openrouter_integration.list_models()

            # Create agent classes for each model
            if models and isinstance(models, list):
                if include_models:
                    models = [m for m in models if m.get("id") in include_models]
                    logger.info(
                        f"Filtered to {len(models)} models (include_models={include_models})"
                    )
                logger.info(f"Creating {len(models)} agent classes from models...")
                for model_data in models:
                    architecture = model_data.get("architecture", {})
                    input_modalities = architecture.get("input_modalities", [])
                    supported_parameters = model_data.get("supported_parameters", [])

                    # Skip models that don't support text input OR don't support tools
                    if (
                        "text" not in input_modalities
                        or "tools" not in supported_parameters
                    ):
                        continue

                    try:
                        agent_cls = self._create_model_agent_class(model_data)
                        agents.append(agent_cls)
                    except Exception as e:
                        logger.warning(
                            f"Failed to create agent for model {model_data.get('id', 'unknown')}: {e}"
                        )
                        continue

                logger.info(f"Successfully created {len(agents)} model agents")
            else:
                logger.warning("No models available to create agents from")

        except Exception as e:
            logger.error(f"Error loading models and creating agents: {e}")

        return agents
