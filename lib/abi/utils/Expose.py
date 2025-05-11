from abc import ABC, abstractmethod

from fastapi import APIRouter
from langchain_core.tools import StructuredTool


class Expose(ABC):
    @abstractmethod
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of StructuredTools that can be used by an Agent.

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
        route_name: str,
        name: str,
        description: str = "",
        description_stream: str = "",
        tags: list[str] = [],
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
