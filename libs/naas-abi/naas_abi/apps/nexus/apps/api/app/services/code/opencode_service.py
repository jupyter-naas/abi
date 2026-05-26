from __future__ import annotations

import asyncio

from naas_abi.apps.nexus.apps.api.app.services.code.adapters.secondary.opencode_http import (
    OpencodeHttpAdapter,
    first_available_model,
    lookup_model_name,
    parse_model_ref,
)
from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeOpencodeChatInput,
    CodeOpencodeDefaultModelData,
)
from naas_abi.apps.nexus.apps.api.app.services.code.port import CodeOpencodePort
from naas_abi.apps.nexus.apps.api.app.services.code.workdir_sync_service import (
    CodeWorkdirSyncService,
)


class CodeOpencodeService:
    def __init__(
        self,
        adapter: CodeOpencodePort,
        sync_service: CodeWorkdirSyncService | None = None,
    ):
        self.adapter = adapter
        self._sync = sync_service

    async def health(self) -> dict[str, object]:
        return await self.adapter.health()

    async def list_providers(self) -> object:
        return await self.adapter.proxy_get("config/providers")

    async def list_sessions(self) -> object:
        return await self.adapter.proxy_get("session")

    async def session_messages(self, session_id: str) -> object:
        return await self.adapter.proxy_get(f"session/{session_id}/messages")

    async def delete_session(self, session_id: str) -> object:
        return await self.adapter.proxy_delete(f"session/{session_id}")

    async def abort_session(self, session_id: str) -> object:
        return await self.adapter.proxy_post(f"session/{session_id}/abort")

    async def revert_session(self, session_id: str, message_id: str = "") -> object:
        payload: dict = {}
        if message_id:
            payload["messageID"] = message_id
        return await self.adapter.proxy_post(f"session/{session_id}/revert", payload)

    async def fork_session(self, session_id: str, message_id: str = "") -> object:
        payload: dict = {}
        if message_id:
            payload["messageID"] = message_id
        return await self.adapter.proxy_post(f"session/{session_id}/fork", payload)

    async def session_diff(self, session_id: str, message_id: str = "") -> object:
        path = f"session/{session_id}/diff"
        if message_id:
            from urllib.parse import quote

            path = f"{path}?messageID={quote(message_id, safe='')}"
        return await self.adapter.proxy_get(path)

    async def session_children(self, session_id: str) -> object:
        return await self.adapter.proxy_get(f"session/{session_id}/children")

    async def create_session(self, title: str = "", parent_id: str = "") -> object:
        payload: dict = {}
        if title:
            payload["title"] = title
        if parent_id:
            payload["parentID"] = parent_id
        return await self.adapter.proxy_post("session", payload)

    async def default_model(self) -> CodeOpencodeDefaultModelData:
        if not isinstance(self.adapter, OpencodeHttpAdapter):
            raise TypeError("default_model requires OpencodeHttpAdapter")

        agent = self.adapter._get_agent()
        provider_id = ""
        model_id = ""
        name = ""
        source = "auto"

        parsed = parse_model_ref(agent.conf.model)
        if parsed:
            provider_id, model_id = parsed
            name = model_id
            source = "engine"

        try:
            await self.adapter.resolve_base_url()
            cfg = await self.adapter.proxy_get("config")
            if isinstance(cfg, dict):
                model_val = cfg.get("model")
                if isinstance(model_val, str):
                    cfg_parsed = parse_model_ref(model_val)
                    if cfg_parsed:
                        provider_id, model_id = cfg_parsed
                        name = model_id
                        source = "opencode"

            providers_data = await self.adapter.proxy_get("config/providers")
            if provider_id and model_id:
                name = lookup_model_name(providers_data, provider_id, model_id)
            else:
                first = first_available_model(providers_data)
                if first:
                    provider_id, model_id, name = first
        except Exception:
            if not name:
                name = model_id

        return CodeOpencodeDefaultModelData(
            provider_id=provider_id,
            model_id=model_id,
            name=name or model_id,
            source=source,
        )

    async def stream_chat(self, input_data: CodeOpencodeChatInput):
        loop = asyncio.get_running_loop()
        if self._sync and input_data.user_id:
            await loop.run_in_executor(None, self._sync.pull, input_data.user_id)
            if isinstance(self.adapter, OpencodeHttpAdapter):
                self.adapter.set_workdir(self._sync.opencode_workdir(input_data.user_id))
        try:
            async for event in self.adapter.stream_chat(input_data):
                yield event
        finally:
            if self._sync and input_data.user_id:
                await loop.run_in_executor(None, self._sync.push, input_data.user_id)
