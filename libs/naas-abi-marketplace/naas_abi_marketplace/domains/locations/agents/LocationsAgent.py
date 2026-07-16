from typing import Optional

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)

NAME = "LocationsAgent"
DESCRIPTION = "An helpful agent that can help you with your tasks."
SYSTEM_PROMPT = """
You are LocationsAgent.
"""

class LocationsAgent(Agent):

    @classmethod
    def New(cls, agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> "LocationsAgent":
        from naas_abi_marketplace.domains.locations import ABIModule
        from naas_abi_marketplace.domains.locations.integrations.CLDRIntegration import (
            CLDRIntegration,
            CLDRIntegrationConfiguration,
        )
        from naas_abi_marketplace.domains.locations.integrations.GeoNamesIntegration import (
            GeoNamesIntegration,
            GeoNamesIntegrationConfiguration,
        )
        from naas_abi_marketplace.domains.locations.integrations.GeonamescacheIntegration import (
            GeonamescacheIntegration,
            GeonamescacheIntegrationConfiguration,
        )
        from naas_abi_marketplace.domains.locations.integrations.PgeocodeIntegration import (
            PgeocodeIntegration,
            PgeocodeIntegrationConfiguration,
        )
        from naas_abi_marketplace.domains.locations.pipelines.LocationsPipeline import (
            LocationsPipeline,
            LocationsPipelineConfiguration,
        )
        from naas_abi_marketplace.domains.locations.workflows.LocationsWorkflow import (
            LocationsWorkflow,
            LocationsWorkflowConfiguration,
        )

        # Set model
        from naas_abi_marketplace.ai.chatgpt.models.gpt_5 import model as chatgpt_model

        model = chatgpt_model.model

        # Use provided configuration or create default one
        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

        # Use provided shared state or create new one
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState()

        tools: list = []
        tools += GeoNamesIntegration.as_tools(GeoNamesIntegrationConfiguration())
        tools += PgeocodeIntegration.as_tools(PgeocodeIntegrationConfiguration())
        tools += GeonamescacheIntegration.as_tools(GeonamescacheIntegrationConfiguration())
        tools += CLDRIntegration.as_tools(CLDRIntegrationConfiguration())

        locations_pipeline = LocationsPipeline(LocationsPipelineConfiguration())
        tools += locations_pipeline.as_tools()

        abi_module = ABIModule.get_instance()
        locations_workflow = LocationsWorkflow(
            LocationsWorkflowConfiguration(
                triple_store=abi_module.engine.services.triple_store,
                vector_store=abi_module.engine.services.vector_store,
                secret=abi_module.engine.services.secret,
            )
        )
        tools += locations_workflow.as_tools()

        agents: list = []

        return cls(
            name=NAME,
            description=DESCRIPTION,
            chat_model=model,
            tools=tools,
            agents=agents,
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )