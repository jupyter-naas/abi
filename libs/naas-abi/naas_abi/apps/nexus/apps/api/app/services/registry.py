from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import (
    PostgresSessionRegistry,
)
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from naas_abi.apps.nexus.apps.api.app.services.agents.service import AgentService
    from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
    from naas_abi.apps.nexus.apps.api.app.services.graph.service import GraphService
    from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMService
    from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
    from naas_abi.apps.nexus.apps.api.app.services.search.service import SearchService
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService


@dataclass(frozen=True)
class RegistryServices:
    iam: IAMService
    chat: ChatService
    search: SearchService
    agents: AgentService
    workspaces: WorkspaceService
    organizations: OrganizationService
    graph: GraphService


class ServiceRegistry:
    _instance: ServiceRegistry | None = None

    def __init__(self, services: RegistryServices):
        self._services = services

    @classmethod
    def configure(cls, services: RegistryServices) -> ServiceRegistry:
        cls._instance = cls(services=services)
        return cls._instance

    @classmethod
    def instance(cls) -> ServiceRegistry:
        if cls._instance is None:
            raise RuntimeError("ServiceRegistry is not configured")
        return cls._instance

    @property
    def iam(self) -> IAMService:
        return self._services.iam

    @property
    def chat(self) -> ChatService:
        return self._services.chat

    @property
    def agents(self) -> AgentService:
        return self._services.agents

    @property
    def search(self) -> SearchService:
        return self._services.search

    @property
    def workspaces(self) -> WorkspaceService:
        return self._services.workspaces

    @property
    def organizations(self) -> OrganizationService:
        return self._services.organizations

    @property
    def graph(self) -> GraphService:
        return self._services.graph


async def get_service_registry(db: AsyncSession = Depends(get_db)):
    registry = ServiceRegistry.instance()
    session_registry = PostgresSessionRegistry.instance()
    session_id = f"sess-{uuid4().hex}"
    session_registry.bind(session_id=session_id, db=db)
    token = session_registry.set_current_session(session_id)
    try:
        yield registry
    finally:
        session_registry.reset_current_session(token)
        session_registry.unbind(session_id)
