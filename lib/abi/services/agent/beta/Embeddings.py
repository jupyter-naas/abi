import os
from typing import List, Optional
from abc import ABC, abstractmethod

# Lazy imports to avoid startup dependencies
_sentence_transformer = None
_openai_embeddings = None

class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        pass
    
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        pass

class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """HuggingFace SentenceTransformers embedding provider."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        global _sentence_transformer
        if _sentence_transformer is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                _sentence_transformer = SentenceTransformer(model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        self.model = _sentence_transformer
    
    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        return self.model.encode(text).tolist()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        return self.model.encode(texts).tolist()

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider (fallback option)."""
    
    def __init__(self):
        global _openai_embeddings
        if _openai_embeddings is None:
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError(
                    "OPENAI_API_KEY environment variable is required for OpenAI embeddings. "
                    "Set it or use a different embedding strategy."
                )
            from langchain_openai import OpenAIEmbeddings
            _openai_embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
        self.model = _openai_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        return self.model.embed_query(text)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        return self.model.embed_documents(texts)

class EmbeddingService:
    """Main embedding service with provider abstraction."""
    
    def __init__(self, provider: Optional[str] = None):
        if provider is None:
            # Default to HuggingFace, fallback to OpenAI if available
            provider = "huggingface"
            if os.getenv("OPENAI_API_KEY") and os.getenv("EMBEDDING_FALLBACK_TO_OPENAI", "true").lower() == "true":
                provider = "openai"
        
        self.provider = self._get_provider(provider)
    
    def _get_provider(self, provider: str) -> EmbeddingProvider:
        """Get embedding provider based on configuration."""
        if provider == "huggingface":
            return HuggingFaceEmbeddingProvider()
        elif provider == "openai":
            return OpenAIEmbeddingProvider()
        else:
            raise ValueError(f"Unknown embedding provider: {provider}")
    
    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single text query."""
        return self.provider.embed_query(text)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        return self.provider.embed_documents(texts)

# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None

def _get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

def openai_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts (backward compatibility)."""
    service = _get_embedding_service()
    return service.embed_documents(texts)

def openai_embeddings(text: str) -> List[float]:
    """Generate embeddings for text (backward compatibility)."""
    service = _get_embedding_service()
    return service.embed_query(text)

