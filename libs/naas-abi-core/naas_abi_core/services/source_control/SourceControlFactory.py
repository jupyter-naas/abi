from __future__ import annotations

from naas_abi_core.services.source_control.adapters.secondary.ForgejoAdapter import (
    ForgejoAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)


class SourceControlFactory:
    @staticmethod
    def SourceControlServiceForgejo(
        *,
        base_url: str,
        admin_token: str,
        organization: str = "",
        timeout: int = 30,
    ) -> SourceControlService:
        return SourceControlService(
            ForgejoAdapter(
                base_url=base_url,
                admin_token=admin_token,
                organization=organization,
                timeout=timeout,
            )
        )

    @staticmethod
    def SourceControlServiceInMemory() -> SourceControlService:
        return SourceControlService(InMemoryAdapter())
