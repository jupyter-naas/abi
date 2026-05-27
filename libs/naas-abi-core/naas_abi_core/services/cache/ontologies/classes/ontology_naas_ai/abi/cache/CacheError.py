from naas_abi_core.services.cache.ontologies.modules.CacheEventOntology import (
    CacheError as _CacheError,
)


class CacheError(_CacheError):
    """Action class for CacheError"""

    def actions(self):
        """Action method - implement your logic here"""
        pass
