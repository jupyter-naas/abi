import logging
import os
from typing import Optional

from .IVectorStorePort import IVectorStorePort
from .VectorStoreService import VectorStoreService
@
logger = logging.getLogger(__name__)


class VectorStoreFactory:
    _instance: Optional[VectorStoreService] = None

    @classmethod
    def create_adapter(cls) -> IVectorStorePort:
        adapter_type = os.getenv("VECTOR_STORE_ADAPTER", "qdrant").lower()

        if adapter_type == "qdrant":
            # Lazy import to avoid loading qdrant_client at module import time
            from .adapters.QdrantAdapter import QdrantAdapter

            host = os.getenv("QDRANT_HOST", "localhost")
            port = int(os.getenv("QDRANT_PORT", "6333"))
            api_key = os.getenv("QDRANT_API_KEY")
            https = os.getenv("QDRANT_HTTPS", "false").lower() == "true"
            timeout = int(os.getenv("QDRANT_TIMEOUT", "30"))

            logger.info(f"Creating Qdrant adapter (host={host}, port={port})")
            return QdrantAdapter(
                host=host, port=port, api_key=api_key, https=https, timeout=timeout
            )
        else:
            raise ValueError(f"Unknown vector store adapter: {adapter_type}")

    @classmethod
    def get_service(cls) -> VectorStoreService:
        if cls._instance is None:
            adapter = cls.create_adapter()
            cls._instance = VectorStoreService(adapter)
            logger.info("VectorStoreService singleton created")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance:
            logger.info("Resetting VectorStoreService singleton")
        cls._instance = None
