"""Pennylane (in-engine). Deprecated: use the remote module
``naas_abi_apps.pennylane`` (module id ``applications.pennylane``) from
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

        module: naas_abi_marketplace.applications.pennylane
        enabled: true
        config:
            pennylane_api_key: "{{ secret.PENNYLANE_API_KEY }}"
        """
        pennylane_api_key: str
        datastore_path: str = "pennylane"
