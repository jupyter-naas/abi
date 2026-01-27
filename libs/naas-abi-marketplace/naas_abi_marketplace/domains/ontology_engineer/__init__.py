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
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
        ],
        services=[ObjectStorageService, TripleStoreService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.domains.support
        enabled: true
        config:
            datastore_path: "ontology-engineer"
        """

        datastore_path: str = "ontology-engineer"

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
