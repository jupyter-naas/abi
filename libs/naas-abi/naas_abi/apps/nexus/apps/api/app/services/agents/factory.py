from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.secondary.postgres import (
    AgentSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.service import AgentService
from sqlalchemy.ext.asyncio import AsyncSession


class AgentFactory:
    @staticmethod
    def ServicePostgres(db: AsyncSession) -> AgentService:
        return AgentService(AgentSecondaryAdapterPostgres(db))
