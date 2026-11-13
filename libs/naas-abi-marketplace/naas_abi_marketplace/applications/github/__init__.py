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

        module: naas_abi_marketplace.applications.github
        enabled: true
        config:
            github_access_token: "{{ secret.GITHUB_ACCESS_TOKEN }}"
            # Optional: the only repositories the agent reaches.
            repositories: ["my-org/my-repo"]
            # Optional: write tools the agent carries besides the read tools.
            agent_write_tools: ["github_create_issue"]
        """

        github_access_token: str
        datastore_path: str = "github"
        # Everyone who may use the GitHub agent acts with this module's token.
        # The agent carries the read tools of GitHubIntegration (READ_TOOLS)
        # and, besides, only the write tools named here.
        agent_write_tools: list[str] = []
        # When not empty, the agent reaches only these repositories ("owner/repo").
        repositories: list[str] = []
