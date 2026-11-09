"""Git: stays an in-engine module (jupyter-naas/abi#1423).

Its agents run ``git``, ``make`` and ``gh`` in the working directory of the
process that loads them: ``abi chat naas_abi_marketplace.applications.git
GitAgent`` in a project (``make commit``, ``make pr``). A remote module runs in
another process, often a container, so it is not ported.
"""

from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[ObjectStorageService, Secret],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.git
        enabled: true
        config:
            datastore_path: "git"
        """

        datastore_path: str = "git"
