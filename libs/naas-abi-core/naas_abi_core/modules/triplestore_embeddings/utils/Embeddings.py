import hashlib
import uuid

import numpy as np
from langchain_core.embeddings import Embeddings
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType

cache = CacheFactory.CacheFS_find_storage(subpath="triple_embeddings")


class EmbeddingsUtils:
    def __init__(self, embeddings_model: Embeddings):
        self.embeddings_model = embeddings_model

    @cache(
        lambda self, text: text,
        cache_type=DataType.PICKLE,
    )
    def create_vector_embedding(self, text: str) -> np.ndarray:
        """Create a vector embedding for a given text.

        Args:
            text: The text to create a vector embedding for

        Returns:
            The vector embedding
        """
        embedding = self.embeddings_model.embed_query(text)
        embedding_array = np.array(embedding)
        return embedding_array

    @staticmethod
    def create_uuid_from_string(string: str) -> str:
        """Create a UUID from a given string.

        Args:
            string: The string to create a UUID from

        Returns:
            The UUID
        """
        return str(uuid.UUID(hashlib.md5(string.encode()).hexdigest()))
