class VectorStore:
    def __init__(self, dimension=1536):
        """Initialize an in-memory vector store using Qdrant.
        
        Args:
            dimension (int): The dimension of the vectors to be stored.
        """
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
        except ImportError:
            raise ImportError("Please install qdrant-client: pip install qdrant-client")
        
        self.client = QdrantClient(":memory:")  # In-memory Qdrant instance
        self.collection_name = "documents"
        self.dimension = dimension
        
        # Create collection
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.dimension,
                distance=models.Distance.COSINE
            )
        )
        self.next_id = 0
    
    def add_texts(self, texts, metadatas=None, embeddings=None):
        """Add texts to the vector store.
        
        Args:
            texts (List[str]): List of text strings to add
            metadatas (List[dict], optional): Metadata for each text
            embeddings (List[List[float]], optional): Pre-computed embeddings for each text
            
        Returns:
            List[str]: IDs of the added texts
        """
        from qdrant_client.http import models
        
        if embeddings is None:
            raise ValueError("Embeddings must be provided")
        
        if metadatas is None:
            metadatas = [{} for _ in texts]
        
        ids = list(range(self.next_id, self.next_id + len(texts)))
        self.next_id += len(texts)
        
        points = [
            models.PointStruct(
                id=idx,
                vector=embedding,
                payload={"text": text, **metadata}
            )
            for idx, text, metadata, embedding in zip(ids, texts, metadatas, embeddings)
        ]
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        return [str(idx) for idx in ids]
    
    def similarity_search(self, query_embedding, k=4):
        """Search for similar documents using a query embedding.
        
        Args:
            query_embedding (List[float]): The embedding vector to search with
            k (int): Number of results to return
            
        Returns:
            List[dict]: List of documents with their metadata
        """
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=k
        )
        
        return [
            {
                "text": hit.payload.get("text", ""),
                "metadata": {k: v for k, v in hit.payload.items() if k != "text"},
                "score": hit.score
            }
            for hit in results.points
        ]
