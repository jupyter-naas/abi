"""Discover module-level tools under ``tools/``.

#1195 is the CLI scaffold and Nexus list/compose. This loader is the engine
walk those features need: find tool classes, register them on the module.

HTTP is a separate concern. Only ``Expose`` subclasses can grow REST via
``as_api``. A LangChain ``BaseTool`` stays agent-internal.
"""

from __future__ import annotations

from naas_abi_core.module.ModuleComponentLoader import load_subclasses
from naas_abi_core.utils.Expose import Expose


class ModuleToolLoader:
    @classmethod
    def load_tools(cls, class_: type) -> list[type]:
        found: list[type] = []
        seen: set[type] = set()

        for tool_cls in load_subclasses(class_, "tools", Expose):
            if tool_cls not in seen:
                seen.add(tool_cls)
                found.append(tool_cls)

        try:
            from langchain_core.tools import BaseTool
        except ImportError:
            return found

        for tool_cls in load_subclasses(class_, "tools", BaseTool):
            if tool_cls not in seen:
                seen.add(tool_cls)
                found.append(tool_cls)

        return found
