from typing import List

from naas_abi_core import logger
from naas_abi_core.module.Module import BaseModule
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class EngineOntologyLoader:
    @classmethod
    def load_ontologies(
        cls, triple_store: TripleStoreService, modules: List[BaseModule]
    ) -> None:
        logger.debug("Loading ontologies")
        for module in modules:
            for ontology in module.ontologies:
                triple_store.load_schema(ontology)
