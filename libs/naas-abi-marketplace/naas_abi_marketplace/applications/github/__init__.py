"""GitHub (in-engine). Deprecated: use the remote module
``naas_abi_apps.github`` (module id ``applications.github``) from
``libs/naas-abi-marketplace-modules``. The in-engine ``support`` module still
imports these integrations in-process until the cleanup phase of
jupyter-naas/abi#1423.
"""

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
        """

        github_access_token: str
        datastore_path: str = "github"
