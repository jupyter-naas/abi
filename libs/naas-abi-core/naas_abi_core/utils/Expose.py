from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class Expose(ABC):
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
