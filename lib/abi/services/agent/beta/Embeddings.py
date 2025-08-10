import os
from typing import List, Optional
from langchain_openai import OpenAIEmbeddings

# Lazy initialization - only create when needed
_embeddings_model: Optional[OpenAIEmbeddings] = None

def _get_embeddings_model() -> OpenAIEmbeddings:
    """Get or create the embeddings model with proper error handling."""
    global _embeddings_model
    
    if _embeddings_model is None:
        # Check if API key is available
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for embeddings. "
                "Set it or use a different embedding strategy."
            )
        _embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")
    
    return _embeddings_model

def openai_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts using OpenAI's embedding model.
    
    Args:
        texts (List[str]): List of texts to generate embeddings for
        
    Returns:
        List[List[float]]: List of embedding vectors
        
    Raises:
        ValueError: If OPENAI_API_KEY is not set
    """
    model = _get_embeddings_model()
    return model.embed_documents(texts)

def openai_embeddings(text: str) -> List[float]:
    """Generate embeddings for text using OpenAI's embedding model.
    
    Args:
        text (str): The text to generate embeddings for
        
    Returns:
        List[float]: The embedding vector
        
    Raises:
        ValueError: If OPENAI_API_KEY is not set
    """
    model = _get_embeddings_model()
    return model.embed_query(text)

