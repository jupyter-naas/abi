"""Cockpit — S1 workforce analytics example app.

Ships a lightweight static dashboard over SPARQL-shaped JSON (workforce,
birth registry, process graph). Datasets are committed under ``data/`` and
served through ``api/``.

See ``README.md``.
"""

from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)


class ABIModule(BaseModule):
    """Registers Cockpit with the ABI engine.

    The web surface is a standalone static app under ``web/`` with datasets
    served through ``api/`` (``make app-personnel-cockpit`` from
    ``domains/personnel``).
    This module only carries catalog configuration.
    """

    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[])

    class Configuration(ModuleConfiguration):
        """
        module: naas_abi_marketplace.domains.personnel.apps.cockpit
        enabled: true
        config:
            demo_login: "demo@personnel-cockpit.local"
            demo_password: "demo"
        """

        demo_login: str = "demo@personnel-cockpit.local"
        demo_password: str = "demo"

    def api(self, app: FastAPI) -> None:
        from naas_abi_marketplace.domains.personnel.apps.cockpit.api.routes import router

        app.include_router(router, prefix="/api/personnel-cockpit")
