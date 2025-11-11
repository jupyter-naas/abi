from typing import List

from abi import logger
from abi.module.Module import BaseModule
from abi.services.triple_store.TripleStoreService import TripleStoreService


class EngineOntologyLoader:
    @classmethod
    def load_ontologies(
        cls, triple_store: TripleStoreService, modules: List[BaseModule]
    ) -> None:
        logger.debug("Loading ontologies")
        for module in modules:
            for ontology in module.ontologies:
                triple_store.load_schema(ontology)
