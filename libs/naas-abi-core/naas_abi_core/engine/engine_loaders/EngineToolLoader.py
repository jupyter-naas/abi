from collections.abc import Mapping
from typing import Protocol

from naas_abi_core import logger
from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
    ToolPublisher,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import IToolRegistry


class _PublishingModule(Protocol):
    def publish_tools(self, publisher: ToolPublisher) -> None: ...


class EngineToolLoader:
    @classmethod
    def publish_tools(
        cls, registry: IToolRegistry, modules: Mapping[str, _PublishingModule]
    ) -> dict[str, int]:
        """Publish every module's tools under the module's configured name.

        A module that fails to publish is logged and skipped so the others
        still boot; composing an agent that references one of its tools then
        fails explicitly with ``ToolNotFoundError``.
        """
        counts: dict[str, int] = {}
        for name, module in modules.items():
            publisher = ToolPublisher(name)
            try:
                module.publish_tools(publisher)
                publisher.publish_to(registry)
            except Exception as exc:  # noqa: BLE001 - one module must not block boot
                logger.opt(exception=True).error(
                    f"Module '{name}' failed to publish its tools: {exc}"
                )
                continue
            counts[name] = len(publisher.tools)
        logger.debug(f"Tool registry: {sum(counts.values())} tool(s) published")
        return counts
