from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService
from naas_abi.apps.nexus.apps.api.app.services.gatekeeper.port import (
    GatekeeperGrantCreateInput,
    GatekeeperGrantRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext
from naas_abi_core.engine.context import get_default_gatekeeper_service
from naas_abi_core.services.gatekeeper.GatekeeperPort import GatekeeperResource


class GatekeeperUnavailableError(RuntimeError):
    pass


class GatekeeperNexusService:
    def __init__(self, chat_service: ChatService) -> None:
        self._chat = chat_service

    async def _ensure_conversation_access(
        self,
        context: RequestContext,
        workspace_id: str,
        conversation_id: str,
    ) -> None:
        await self._chat._ensure_workspace_access(
            context=context,
            workspace_id=workspace_id,
            action="chat.conversation.read",
        )
        conversation = await self._chat.get_conversation_for_user(
            context=context,
            conversation_id=conversation_id,
        )
        if conversation is None or conversation.workspace_id != workspace_id:
            raise PermissionError("Conversation not found")

    def _core(self):
        gatekeeper = get_default_gatekeeper_service()
        if gatekeeper is None:
            raise GatekeeperUnavailableError("Gatekeeper service is not configured")
        return gatekeeper

    async def list_grants(
        self,
        context: RequestContext,
        workspace_id: str,
        conversation_id: str,
    ) -> list[GatekeeperGrantRecord]:
        await self._ensure_conversation_access(context, workspace_id, conversation_id)
        grants = self._core().list_grants(conversation_id)
        return [
            GatekeeperGrantRecord(
                chat_id=grant.chat_id,
                resource_type=grant.resource_type,
                resource_id=grant.resource_id,
                actions=tuple(sorted(grant.actions)),
                granted_at=grant.granted_at,
            )
            for grant in grants
        ]

    async def grant_resource(
        self,
        context: RequestContext,
        workspace_id: str,
        conversation_id: str,
        data: GatekeeperGrantCreateInput,
    ) -> GatekeeperGrantRecord:
        await self._ensure_conversation_access(context, workspace_id, conversation_id)
        grant = self._core().grant_resource(
            conversation_id,
            GatekeeperResource(type=data.resource_type, id=data.resource_id),
            frozenset(data.actions),
        )
        return GatekeeperGrantRecord(
            chat_id=grant.chat_id,
            resource_type=grant.resource_type,
            resource_id=grant.resource_id,
            actions=tuple(sorted(grant.actions)),
            granted_at=grant.granted_at,
        )
