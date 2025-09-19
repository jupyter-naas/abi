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
        """Embed a list of documents."""
        payload = {
            "texts": texts,
            "model": self.model_name
        }
        
        try:
            response = requests.post(
                f"{self.endpoint}/embed",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            embeddings = result.get("embeddings", [])
            
            if len(embeddings) != len(texts):
                raise RuntimeError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")
            
            return embeddings
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Docker Model Runner embedding API error: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Invalid response format from Docker Model Runner: {e}")
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        embeddings = self.embed_documents([text])
        return embeddings[0]
