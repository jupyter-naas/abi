from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import (
    PostgresSessionRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.secondary.postgres import (
    AgentSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.service import AgentService
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.postgres import (
    ChatSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.iam.adapters.secondary.postgres import (
    IAMSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMService
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    RegistryServices,
    ServiceRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService


def initialize_nexus_service_registry() -> ServiceRegistry:
    try:
        return ServiceRegistry.instance()
    except RuntimeError:
        pass

    def db_getter():
        return PostgresSessionRegistry.instance().current_session()

    iam_service = IAMService(IAMSecondaryAdapterPostgres(db_getter=db_getter))
    workspace_service = WorkspaceService(WorkspaceSecondaryAdapterPostgres(db_getter=db_getter))
    organization_service = OrganizationService(
        OrganizationSecondaryAdapterPostgres(db_getter=db_getter)
    )
    chat_service = ChatService(
        adapter=ChatSecondaryAdapterPostgres(db_getter=db_getter),
        iam_service=iam_service,
    )
    agents_service = AgentService(AgentSecondaryAdapterPostgres(db_getter=db_getter))

    return ServiceRegistry.configure(
        RegistryServices(
            iam=iam_service,
            chat=chat_service,
            agents=agents_service,
            workspaces=workspace_service,
            organizations=organization_service,
        )
    )
