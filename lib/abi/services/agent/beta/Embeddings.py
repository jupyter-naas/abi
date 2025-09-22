import os
import hashlib

from lib.abi.services.cache.CacheFactory import CacheFactory
from lib.abi.services.cache.CachePort import DataType
from tqdm import tqdm

cache = CacheFactory.CacheFS_find_storage(subpath="intent_mapping")

def _sha1(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def _sha1s(texts):
    key = ""
    
    for text in texts:
        key += _sha1(text)
    
    return _sha1(key)
    

if os.environ.get("AI_MODE") == "airgap":
    import requests


    @cache(lambda text: _sha1(text), cache_type=DataType.PICKLE)
    def embeddings(text) -> list[float]:
        res = requests.post("http://localhost:12434/engines/llama.cpp/v1/embeddings", json={
            "model": "ai/embeddinggemma",
            "input": text 
        })
        res.raise_for_status()
        
        return res.json()["data"][0]["embedding"]
        
    # @cache(lambda texts: _sha1s(texts), cache_type=DataType.PICKLE)
    def embeddings_batch(texts) -> list[list[float]]:
        ret = []
        
        for text in tqdm(texts, "Embedding intents"):
            ret.append(embeddings(text))

        return ret

else:
    from langchain_openai import OpenAIEmbeddings
    embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")


    @cache(lambda texts: _sha1s(texts), cache_type=DataType.PICKLE)
    def embeddings_batch(texts):
        for e in tqdm([texts], "Embedding intents"):
            return embeddings_model.embed_documents(e)
    
    @cache(lambda text: _sha1(text), cache_type=DataType.PICKLE)
    def embeddings(text):
        """Generate embeddings for text using OpenAI's embedding model.
        
        Args:
            text (str): The text to generate embeddings for
            
        Returns:
            List[float]: The embedding vector
        """

        return embeddings_model.embed_query(text)


