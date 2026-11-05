"""Naas (in-engine). Deprecated for its agent and integration: use the remote
module ``naas_abi_apps.naas`` (module id ``applications.naas``) from
``libs/naas-abi-marketplace-modules``. The ontology YAML workflows stay here
for the in-engine ``ontology_engineer`` and ``powerpoint`` (jupyter-naas/abi#1423).
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
        services=[Secret, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.naas
        enabled: true
        config:
            naas_api_key: "{{ secret.NAAS_API_KEY }}"
            workspace_id: "{{ secret.WORKSPACE_ID }}"
            storage_name: "{{ secret.STORAGE_NAME }}"
        """

        naas_api_key: str
        workspace_id: str | None = None
        storage_name: str | None = None
        datastore_path: str = "naas"
