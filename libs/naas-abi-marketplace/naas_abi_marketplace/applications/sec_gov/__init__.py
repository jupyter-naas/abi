"""SEC EDGAR (in-engine). Deprecated: use the remote module
``naas_abi_apps.sec_gov`` (module id ``applications.sec_gov``) from
``libs/naas-abi-marketplace-modules``. This module is removed in the cleanup
phase of jupyter-naas/abi#1423.
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

        module: naas_abi_marketplace.applications.sec_gov
        enabled: true
        config:
            user_agent: "NAAS-ABI-Marketplace/1.0 (florent@naas.ai)"
            datastore_path: "sec_gov"
        """

        user_agent: str
        datastore_path: str = "sec_gov"
