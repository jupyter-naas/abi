from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    """People intelligence: what can be known about any person.

    The vocabulary and pipelines for acts of working, studying and
    certification, skills, languages and published profiles, whoever employs
    the person. An organization's internal records about its own staff live in
    ``naas_abi_marketplace.domains.personnel``, which specializes these classes.
    """

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            # PeopleAgent.get_tools() resolves its SPARQL tools through this
            # module, so it must be loaded before the agent is built.
            "naas_abi_core.modules.templatablesparqlquery",
        ],
        services=[
            TripleStoreService,
            ObjectStorageService,
        ],
    )

    class Configuration(ModuleConfiguration):
        """
        module: naas_abi_marketplace.domains.intelligence.modules.people
        enabled: true
        """

        datastore_path: str = "intelligence/people"
        ontology_namespace: str = "http://ontology.naas.ai/people/"
        graph_name: str = "http://ontology.naas.ai/graph/people"

    def api(self, app: FastAPI) -> None:
        """Serve stored portraits at the URLs PersonPortraitPipeline records."""
        from naas_abi_marketplace.domains.intelligence.modules.people.utils.portrait_routes import (
            mount_portrait_route,
        )

        mount_portrait_route(
            app,
            lambda: self.engine.services.object_storage,
            self.configuration.datastore_path,
        )
