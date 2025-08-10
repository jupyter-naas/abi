from langchain_openai import OpenAIEmbeddings

embeddings_model = OpenAIEmbeddings(model="text-embedding-ada-002")


def openai_embeddings_batch(texts):
    return embeddings_model.embed_documents(texts)

def openai_embeddings(text):
    """Generate embeddings for text using OpenAI's embedding model.
    
    Args:
        text (str): The text to generate embeddings for
        
    Returns:
        List[float]: The embedding vector
    """

    embedding = embeddings_model.embed_query(text)
    
    return embedding

