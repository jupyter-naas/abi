from __future__ import annotations

from typing import TYPE_CHECKING

from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

if TYPE_CHECKING:
    from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
        ToolPublisher,
    )


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.github
        enabled: true
        config:
            github_access_token: "{{ secret.GITHUB_ACCESS_TOKEN }}"
        """

        github_access_token: str
        datastore_path: str = "github"

    def publish_tools(self, publisher: ToolPublisher) -> None:
        """Publish the REST and GraphQL integration tools to the tool registry.

        Agents composed from records can bind them without ``GitHubAgent``.
        The module's token is the default; a record may pass its own
        ``access_token`` as a secret reference instead.
        """
        from naas_abi_core.services.tool_registry.ToolRegistryPort import (
            ConfigRequirement,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
            GitHubGraphqlIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
            as_tools as graphql_tools,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
            GitHubIntegrationConfiguration,
        )
        from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
            as_tools as rest_tools,
        )

        super().publish_tools(publisher)
        token = [
            ConfigRequirement(
                key="access_token",
                secret=True,
                description="GitHub personal access token",
            )
        ]
        defaults = {"access_token": self.configuration.github_access_token}
        publisher.add_factory(
            lambda config: rest_tools(
                GitHubIntegrationConfiguration(access_token=config["access_token"])
            ),
            default_config=defaults,
            requirements=token,
            tags=("github", "vcs"),
        )
        publisher.add_factory(
            lambda config: graphql_tools(
                GitHubGraphqlIntegrationConfiguration(
                    access_token=config["access_token"]
                )
            ),
            default_config=defaults,
            requirements=token,
            tags=("github", "projects"),
        )
