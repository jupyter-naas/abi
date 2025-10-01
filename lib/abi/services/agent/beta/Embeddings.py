import os
import hashlib

from lib.abi.services.cache.CacheFactory import CacheFactory
from lib.abi.services.cache.CachePort import DataType
from tqdm import tqdm

cache = CacheFactory.CacheFS_find_storage(subpath="intent_mapping")

EMBEDDINGS_MODELS_DIMENSIONS_MAP = {
    "ai/embeddinggemma": 768,
    "text-embedding-ada-002": 1536,
}

def __get_safe_model(model: str):
    """
    Returns a sanitized version of the model name suitable for use in cache keys.

    Args:
        model (str): The model name to sanitize.

    Returns:
        str: The sanitized model name.

    Raises:
        AssertionError: If the model is not in the EMBEDDINGS_MODELS_DIMENSIONS_MAP.
    """
    assert model in EMBEDDINGS_MODELS_DIMENSIONS_MAP, f"Model {model} not supported. You need to add it to the EMBEDDINGS_MODELS_DIMENSIONS_MAP in Embeddings.py"
    return "".join([c if c.isalnum() or c in ('-', '_') else '_' for c in model])

def __compute_key(safe_model: str, dimensions: int, text: str):
    """
    Computes a unique cache key for a given model and text.

    Args:
        safe_model (str): The sanitized model name.
        text (str): The input text.

    Returns:
        str: The computed cache key.
    """
    return f'{safe_model}_{dimensions}_{hashlib.sha1(text.encode("utf-8")).hexdigest()}'

def _sha1s(model: str):
    """
    Returns a function that computes a combined cache key for a list of texts for a given model.

    Args:
        model (str): The model name.

    Returns:
        Callable[[list[str]], str]: A function that takes a list of texts and returns a combined cache key.
    """
    safe_model = __get_safe_model(model)

    def func(texts):
        """
        Computes a combined cache key for a list of texts.

        Args:
            texts (list[str]): The list of input texts.

        Returns:
            str: The combined cache key.
        """
        key = ""
        for text in texts:
            key += __compute_key(safe_model, EMBEDDINGS_MODELS_DIMENSIONS_MAP[model], text)
        return key

    return func

def _sha1(model: str):  
    """
    Returns a function that computes a cache key for a single text for a given model.

    Args:
        model (str): The model name.

    Returns:
        Callable[[str], str]: A function that takes a text and returns a cache key.
    """
    safe_model = __get_safe_model(model)

    def func(text):
        """
        Computes a cache key for a single text.

        Args:
            text (str): The input text.

        Returns:
            str: The cache key.
        """
        return __compute_key(safe_model, EMBEDDINGS_MODELS_DIMENSIONS_MAP[model], text)

    return func

if os.environ.get("AI_MODE") == "airgap":
    import requests
        
    @cache(_sha1("ai/embeddinggemma"), cache_type=DataType.PICKLE)
    def embeddings(text) -> list[float]:
        res = requests.post("http://localhost:12434/engines/llama.cpp/v1/embeddings", json={
            "model": "ai/embeddinggemma",
            "input": text 
        })
        res.raise_for_status()
        return res.json()["data"][0]["embedding"]
        
    @cache(_sha1s("ai/embeddinggemma"), cache_type=DataType.PICKLE)
    def embeddings_batch(texts) -> list[list[float]]:
        ret = []
        
        for text in tqdm(texts, "Embedding intents"):
            ret.append(embeddings(text))

        return ret

else:
    from langchain_openai import OpenAIEmbeddings
    
    # Lazy initialization to avoid import-time API key requirement
    _embeddings_model = None
    
    def _get_embeddings_model():
        global _embeddings_model
        if _embeddings_model is None:
            _embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")
        return _embeddings_model

    @cache(_sha1s("text-embedding-ada-002"), cache_type=DataType.PICKLE)
    def embeddings_batch(texts):
        for e in tqdm([texts], "Embedding intents"):
            return _get_embeddings_model().embed_documents(e)
    
    @cache(_sha1("text-embedding-ada-002"), cache_type=DataType.PICKLE)
    def embeddings(text):
        """Generate embeddings for text using OpenAI's embedding model.
        
        Args:
            text (str): The text to generate embeddings for
            
        Returns:
            List[float]: The embedding vector
        """

        return _get_embeddings_model().embed_query(text)


