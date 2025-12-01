from naas_abi_core.utils.SPARQL import SPARQLUtils
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.applications.linkedin import ABIModule


class BasePipeline:
    sparql_utils: SPARQLUtils
    storage_utils: StorageUtils

    def __init__(self) -> None:
        module: ABIModule = ABIModule.get_instance()

        self.sparql_utils = SPARQLUtils(module.engine.services.triple_store)
        self.storage_utils = StorageUtils(module.engine.services.object_storage)
        self.storage_utils = StorageUtils(module.engine.services.object_storage)
