from naas_abi_core.services.vector_store.ontologies.modules.VectorStoreEventOntology import (
    VectorStoreError as _VectorStoreError,
)


class VectorStoreError(_VectorStoreError):
    """Action class for VectorStoreError"""

    def actions(self):
        """Action method - implement your logic here"""
        pass
