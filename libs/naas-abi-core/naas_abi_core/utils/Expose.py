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

    @abstractmethod
    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = [],
    ) -> None:
        """Registers API routes for the class's functionality on the provided FastAPI router.

        This method should be implemented by concrete classes to expose their functionality
        via HTTP endpoints using FastAPI. The method should register routes on the provided
        router that allow accessing the class's functionality through HTTP requests.

        Args:
            router (APIRouter): The FastAPI router on which to register the routes

        Returns:
            None

        Raises:
            NotImplementedError: If the concrete class does not implement this method
        """
        raise NotImplementedError()
        raise NotImplementedError()
