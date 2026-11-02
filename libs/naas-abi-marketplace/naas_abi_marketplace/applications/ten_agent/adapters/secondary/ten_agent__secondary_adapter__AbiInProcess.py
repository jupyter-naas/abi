"""``AgentStreamPort`` over the ABI agent running in this API process.

Same entry point as Nexus chat and the OpenAI-compatible gateway
(``stream_with_abi_inprocess``), imported lazily so the module loads without
Nexus installed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from naas_abi_marketplace.applications.ten_agent.domain.ports import (
    AgentMessage,
    AgentStreamPort,
)


class AbiInProcessAgentStream(AgentStreamPort):
    async def stream(
        self,
        agent: str,
        messages: list[AgentMessage],
        thread_id: str,
        preamble: str | None,
    ) -> AsyncIterator[str | dict[str, Any]]:
        from naas_abi.apps.nexus.apps.api.app.services.provider_runtime import (
            Message,
            ProviderConfig,
            stream_with_abi_inprocess,
        )

        config = ProviderConfig(
            id="abi", name="abi", type="abi", enabled=True, model=agent
        )
        async for chunk in stream_with_abi_inprocess(
            [Message(role=m.role, content=m.content) for m in messages],
            config,
            thread_id,
            user_context_preamble=preamble,
        ):
            yield chunk
