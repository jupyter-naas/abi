from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, BinaryIO
import os
import shutil
from datetime import datetime


@dataclass
class LocalObjectStoreConfiguration(IntegrationConfiguration):
    """Configuration for Local Object Store integration.

    Attributes:
        base_path (str): Base directory path for the local object store
    """

    base_path: str


class LocalObjectStoreIntegration(Integration):
    """Local Object Store integration client.

    This integration provides methods to interact with the local file system
    in a way similar to object storage systems.
    """

    __configuration: LocalObjectStoreConfiguration

    def __init__(self, configuration: LocalObjectStoreConfiguration):
        """Initialize Local Object Store with base path."""
        super().__init__(configuration)
        self.__configuration = configuration

        # Ensure base directory exists
        os.makedirs(self.__configuration.base_path, exist_ok=True)

    def list_objects(
        self, prefix: Optional[str] = None, max_keys: int = 1000
    ) -> List[Dict]:
        """List objects in the local store.

        Args:
            prefix (str, optional): Filter objects by prefix
            max_keys (int, optional): Maximum number of files to return

        Returns:
            List[Dict]: List of object information

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            objects = []
            base_path = self.__configuration.base_path
            search_path = os.path.join(base_path, prefix) if prefix else base_path

            for root, _, files in os.walk(search_path):
                for file in files[:max_keys]:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, base_path)
                    stat = os.stat(full_path)

                    objects.append(
                        {
                            "key": rel_path,
                            "size": stat.st_size,
                            "last_modified": datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                            "storage_class": "local",
                        }
                    )

                    if len(objects) >= max_keys:
                        break

            return objects
        except Exception as e:
            raise IntegrationConnectionError(
                f"Local storage operation failed: {str(e)}"
            )

    def get_object(self, key: str) -> bytes:
        """Get object content from local store.

        Args:
            key (str): Object key (relative path)

        Returns:
            bytes: Object content

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            file_path = os.path.join(self.__configuration.base_path, key)
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            raise IntegrationConnectionError(
                f"Local storage operation failed: {str(e)}"
            )

    def save_object(self, key: str, content: Union[str, bytes, BinaryIO]) -> Dict:
        """Save object to local store.

        Args:
            key (str): Object key (relative path)
            content: Content to save (string, bytes, or file-like object)

        Returns:
            Dict: Save result

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            file_path = os.path.join(self.__configuration.base_path, key)

            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            mode = "wb" if isinstance(content, bytes) else "w"
            with open(file_path, mode) as f:
                if hasattr(content, "read"):
                    shutil.copyfileobj(content, f)
                else:
                    f.write(content)

            return {"key": key, "size": os.path.getsize(file_path), "path": file_path}
        except Exception as e:
            raise IntegrationConnectionError(
                f"Local storage operation failed: {str(e)}"
            )

    def delete_object(self, key: str) -> Dict:
        """Delete object from local store.

        Args:
            key (str): Object key (relative path)

        Returns:
            Dict: Deletion result

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            file_path = os.path.join(self.__configuration.base_path, key)
            os.remove(file_path)

            # Try to remove empty parent directories
            parent_dir = os.path.dirname(file_path)
            while parent_dir != self.__configuration.base_path:
                if len(os.listdir(parent_dir)) == 0:
                    os.rmdir(parent_dir)
                    parent_dir = os.path.dirname(parent_dir)
                else:
                    break

            return {"key": key, "deleted": True}
        except Exception as e:
            raise IntegrationConnectionError(
                f"Local storage operation failed: {str(e)}"
            )


def as_tools(configuration: LocalObjectStoreConfiguration):
    """Convert Local Object Store integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = LocalObjectStoreIntegration(configuration)

    class ListObjectsSchema(BaseModel):
        prefix: Optional[str] = Field(None, description="Filter objects by prefix")
        max_keys: int = Field(
            default=1000, description="Maximum number of files to return"
        )

    class ObjectSchema(BaseModel):
        key: str = Field(..., description="Object key (relative path)")

    class SaveObjectSchema(BaseModel):
        key: str = Field(..., description="Object key (relative path)")
        content: str = Field(..., description="Content to save")

    return [
        StructuredTool(
            name="list_local_objects",
            description="List objects in the local store",
            func=lambda prefix, max_keys: integration.list_objects(prefix, max_keys),
            args_schema=ListObjectsSchema,
        ),
        StructuredTool(
            name="get_local_object",
            description="Get object content from local store",
            func=lambda key: integration.get_object(key),
            args_schema=ObjectSchema,
        ),
        StructuredTool(
            name="save_local_object",
            description="Save object to local store",
            func=lambda key, content: integration.save_object(key, content),
            args_schema=SaveObjectSchema,
        ),
        StructuredTool(
            name="delete_local_object",
            description="Delete object from local store",
            func=lambda key: integration.delete_object(key),
            args_schema=ObjectSchema,
        ),
    ]
