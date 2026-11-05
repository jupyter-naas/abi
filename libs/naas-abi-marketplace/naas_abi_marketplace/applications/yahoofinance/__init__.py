"""Yahoo Finance (in-engine). Deprecated: use the remote module
``naas_abi_apps.yahoofinance`` (module id ``applications.yahoofinance``) from
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

        module: naas_abi_marketplace.applications.yahoofinance
        enabled: true
        config:
            datastore_path: "yahoofinance"
        """

        datastore_path: str = "yahoofinance"
