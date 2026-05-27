from naas_abi_core.services.email.ontologies.modules.EmailEventOntology import (
    EmailError as _EmailError,
)


class EmailError(_EmailError):
    """Action class for EmailError"""

    def actions(self):
        """Action method - implement your logic here"""
        pass
