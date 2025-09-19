"""Docker Model Runner Embeddings Adapter for LangChain compatibility."""

import requests
import json
from typing import List
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field


class DockerModelRunnerEmbeddings(BaseModel, Embeddings):
    """Docker Model Runner embeddings adapter for LangChain."""
    
    endpoint: str = Field(description="Docker Model Runner embedding endpoint URL")
    model_name: str = Field(description="Embedding model name identifier")
    
    class Config:
        arbitrary_types_allowed = True
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents using Ollama API (Docker Model Runner backend)."""
        embeddings = []
        
        for text in texts:
            payload = {
                "model": self.model_name,
                "prompt": text
            }
            
            try:
                response = requests.post(
                    f"{self.endpoint}/api/embeddings",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                embedding = result.get("embedding", [])
                
                if not embedding:
                    raise RuntimeError(f"No embedding returned for text: {text[:50]}...")
                
                embeddings.append(embedding)
                
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Docker Model Runner embedding API error: {e}")
            except (KeyError, json.JSONDecodeError) as e:
                raise RuntimeError(f"Invalid response format from Docker Model Runner: {e}")
        
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        embeddings = self.embed_documents([text])
        return embeddings[0]
