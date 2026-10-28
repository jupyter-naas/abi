from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


def _tagged(as_tools):
    """``as_tools`` whose tools name the object that exposed them, so an agent
    finds a module workflow's scope from its tool (``agent.context``)."""

    @functools.wraps(as_tools)
    def wrapper(self, *args, **kwargs):
        from naas_abi_core.services.agent.context import EXPOSED_BY, remember_exposer

        tools = as_tools(self, *args, **kwargs)
        key = remember_exposer(self)
        for tool in tools or () if key else ():
            try:
                tool.metadata = {
                    **(getattr(tool, "metadata", None) or {}),
                    EXPOSED_BY: key,
                }
            except (AttributeError, TypeError, ValueError):
                pass  # a tool that takes no metadata stays unbound
        return tools

    wrapper.__abi_tagged__ = True  # type: ignore[attr-defined]
    return wrapper


class Expose(ABC):
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        own = cls.__dict__.get("as_tools")
        if callable(own) and not getattr(own, "__abi_tagged__", False):
            cls.as_tools = _tagged(own)  # type: ignore[method-assign]

    @abstractmethod
    def as_tools(self) -> list[BaseTool]:
        """Returns a list of Tools that can be used by an Agent.

        This method should be implemented by concrete classes to expose their functionality
        as LangChain StructuredTools that can be used by an Agent.

        Returns:
            list[StructuredTool]: A list of StructuredTools that expose the class's functionality

        Raises:
            NotImplementedError: If the concrete class does not implement this method
        """
        raise NotImplementedError()

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        """Register HTTP routes on ``router``.

        The default implementation posts ``run(parameters)`` when that method
        is a real override with a Pydantic body. Subclasses that need a
        custom surface override this. Stubs that return None are treated as
        empty; the kernel then tries the same default and skips if ``run``
        is not live. See ``naas_abi_core.utils.process_api``.
        """
        from naas_abi_core.utils.process_api import register_run_route

        register_run_route(
            self,
            router,
            route_name=route_name,
            name=name,
            description=description,
            tags=tags,
        )
