from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

# from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService

# from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
# from naas_abi_core.services.bus.BusService import BusService
# from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            # PersonnelAgent.get_tools() resolves its SPARQL tools through this
            # module, so it must be loaded before the agent is built.
            "naas_abi_core.modules.templatablesparqlquery",
        ],
        services=[
            # Secret,
            TripleStoreService,
            ObjectStorageService,
            # VectorStoreService,
            # BusService,
            # KeyValueService,
        ],
    )

    class Configuration(ModuleConfiguration):
        datastore_path: str = "personnel"
        ontology_namespace: str = "http://ontology.naas.ai/personnel/"
        graph_name: str = "http://ontology.naas.ai/graph/personnel"

    # on_initialized is called by the engine after all modules and services have been fully loaded.
    # At this point, you can safely access other modules and services through the engine's interfaces.
    # Override this method to implement any post-initialization logic your module requires.
    def on_initialized(self):
        super().on_initialized()
        # Resolve cockpit data source: ObjectStorage → TripleStore → data/.
        try:
            from naas_abi_marketplace.domains.personnel.sandbox.demo_fallback import (
                resolve_apps_data_root,
            )

            source, root = resolve_apps_data_root(
                object_storage=self.engine.services.object_storage,
                triple_store=self.engine.services.triple_store,
                graph_name=self.configuration.graph_name,
                datastore_path=self.configuration.datastore_path,
            )
            self._cockpit_data_source = source
            self._cockpit_data_root = root
        except Exception:
            self._cockpit_data_source = "web_data"
            self._cockpit_data_root = None

    def cockpit_data_source(self) -> str:
        """``object_storage`` | ``triple_store`` | ``web_data``."""
        return getattr(self, "_cockpit_data_source", "web_data")

    def api(self, app: FastAPI) -> None:
        from naas_abi_marketplace.domains.personnel.apps.cockpit.api.routes import router

        app.include_router(router, prefix="/api/personnel-cockpit")
