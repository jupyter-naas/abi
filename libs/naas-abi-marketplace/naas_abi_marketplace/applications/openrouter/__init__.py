from pydantic import Field

from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.openrouter
        enabled: true
        config:
            openrouter_api_key: "{{ secret.OPENROUTER_API_KEY }}"
            include_models: ["google/gemini-3.1-pro-preview"]  # optional: only create agents for these model ids
        """

        openrouter_api_key: str
        datastore_path: str = "openrouter"
        include_models: list[str] = Field(default_factory=list)

    def on_load(self):
        super().on_load()
        from naas_abi_marketplace.applications.openrouter.agents.OpenRouterAgents import (
            OpenRouterAgents,
        )
        from naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration import (
            OpenRouterAPIIntegration,
            OpenRouterAPIIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.openrouter.models.OpenRouterModel import (
            OpenRouterModel,
        )

        openrouter_integration_configuration = OpenRouterAPIIntegrationConfiguration(
            api_key=self.configuration.openrouter_api_key,
            object_storage=self.engine.services.object_storage,
            datastore_path=self.configuration.datastore_path,
        )
        openrouter_integration = OpenRouterAPIIntegration(
            openrouter_integration_configuration
        )
        openrouter_model = OpenRouterModel(
            api_key=self.configuration.openrouter_api_key
        )
        # Load models and create agent classes
        openrouter_agents = OpenRouterAgents(
            openrouter_integration=openrouter_integration,
            openrouter_model=openrouter_model,
        )
        self.agents.extend(
            openrouter_agents.create_agents(
                include_models=self.configuration.include_models
            )
        )
