from naas_abi_core.services.triple_store.ontologies.modules.TripleStoreEventOntology import (
    TripleStoreError as _TripleStoreError,
)


class TripleStoreError(_TripleStoreError):
    """Action class for TripleStoreError"""

    def actions(self):
        """Action method - implement your logic here"""
        pass
