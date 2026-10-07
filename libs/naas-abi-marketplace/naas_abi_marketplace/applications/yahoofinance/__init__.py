from fastapi import FastAPI
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

    def api(self, app: FastAPI) -> None:
        from naas_abi_marketplace.applications.yahoofinance.apps.screener.api import (
            router,
        )

        app.include_router(router, prefix="/api/yahoofinance/screener")
