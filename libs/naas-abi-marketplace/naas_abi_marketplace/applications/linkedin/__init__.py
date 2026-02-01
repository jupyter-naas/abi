from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class _Configuration(ModuleConfiguration):
    """
    Configuration example:

    module: naas_abi_marketplace.applications.linkedin
    enabled: true
    config:
        li_at: "{{ secret.li_at }}"
        JSESSIONID: "{{ secret.JSESSIONID }}"
        linkedin_profile_url: "https://www.linkedin.com/in/your-profile-id/"
    """

    li_at: str
    JSESSIONID: str
    linkedin_profile_url: str
    datastore_path: str = "linkedin"


class ABIModule(BaseModule[_Configuration]):
    Configuration = _Configuration
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
            "naas_abi_marketplace.applications.google_search",
            "naas_abi_marketplace.applications.naas",
            "naas_abi_core.modules.templatablesparqlquery",
        ],
        services=[ObjectStorageService, TripleStoreService],
    )

    def on_initialized(self):
        super().on_initialized()

        import glob
        import os

        from naas_abi_core import logger
        from naas_abi_core.utils.onto2py import onto2py

        ontologies_dir = os.path.join(os.path.dirname(__file__), "ontologies")
        ttl_files = glob.glob(
            os.path.join(ontologies_dir, "**", "*.ttl"), recursive=True
        )

        if not ttl_files:
            logger.warning(f"No TTL files found in {ontologies_dir}")
            return

        for ttl_file in ttl_files:
            if "Queries.ttl" in ttl_file:
                continue
            try:
                logger.debug(f"Converting {ttl_file} to Python")
                python_code = onto2py(ttl_file)
                py_file = os.path.splitext(ttl_file)[0] + ".py"
                with open(py_file, "w") as f:
                    f.write(python_code)
                logger.debug(f"Successfully converted {ttl_file} to {py_file}")
            except Exception as e:
                logger.error(
                    f"Failed to convert {ttl_file} to Python: {e}", exc_info=True
                )
