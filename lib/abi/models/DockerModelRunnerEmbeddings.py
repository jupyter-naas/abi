"""Docker Model Runner Embeddings Adapter for LangChain compatibility."""

import numpy as np
from typing import List
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field


class DockerModelRunnerEmbeddings(BaseModel, Embeddings):
    """Docker Model Runner embeddings adapter using deterministic embeddings."""
    
    model_name: str = Field(description="Embedding model name identifier")
    
    class Config:
        arbitrary_types_allowed = True
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents using deterministic embeddings."""
        return [self._create_deterministic_embedding(text) for text in texts]
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        return self._create_deterministic_embedding(text)
    
    def _create_deterministic_embedding(self, text: str, dimensions: int = 768) -> List[float]:
        """Create a deterministic embedding based on text hash."""
        text_hash = hash(text) % (2**32)  # Ensure positive 32-bit integer
        np.random.seed(text_hash)
        
        # Generate normalized random vector
        embedding = np.random.normal(0, 1, dimensions)
        embedding = embedding / np.linalg.norm(embedding)  # Normalize to unit vector
        
        return embedding.tolist()
