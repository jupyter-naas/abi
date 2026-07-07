from __future__ import annotations

from naas_abi_core.services.coding_environment.adapters.secondary.CoderAdapter import (
    CoderAdapter,
)
from naas_abi_core.services.coding_environment.adapters.secondary.CodeServerComposeAdapter import (
    CodeServerComposeAdapter,
)
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)


class CodingEnvironmentFactory:
    @staticmethod
    def CodingEnvironmentServiceCoder(
        *,
        access_url: str,
        wildcard_access_url: str,
        admin_token: str,
        organization: str = "default",
        default_template_id: str | None = None,
        default_token_lifetime_seconds: int = 3600,
        workspace_autostop_ms: int = 3_600_000,
        timeout: int = 30,
    ) -> CodingEnvironmentService:
        return CodingEnvironmentService(
            CoderAdapter(
                access_url=access_url,
                wildcard_access_url=wildcard_access_url,
                admin_token=admin_token,
                organization=organization,
                default_template_id=default_template_id,
                default_token_lifetime_seconds=default_token_lifetime_seconds,
                workspace_autostop_ms=workspace_autostop_ms,
                timeout=timeout,
            )
        )

    @staticmethod
    def CodingEnvironmentServiceCodeServer(*, url: str) -> CodingEnvironmentService:
        return CodingEnvironmentService(CodeServerComposeAdapter(url=url))

    @staticmethod
    def CodingEnvironmentServiceInMemory(
        *, polls_until_ready: int = 0
    ) -> CodingEnvironmentService:
        return CodingEnvironmentService(
            InMemoryAdapter(polls_until_ready=polls_until_ready)
        )
