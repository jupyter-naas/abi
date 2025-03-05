use qdrant_client::prelude::*;
use qdrant_client::qdrant::{
    Distance, PointStruct, SearchPoints, VectorParams, VectorsConfig,
};
use anyhow::Result;

pub struct EmbeddingStore {
    client: QdrantClient,
    collection_name: String,
}

impl EmbeddingStore {
    pub async fn new(collection_name: &str, vector_size: u64, in_memory: bool) -> Result<Self> {
        // Create client with either in-memory or persistent storage
        let client = if in_memory {
            QdrantClient::from_url("http://localhost:6334")
                .with_timeout(std::time::Duration::from_secs(60))
                .build()?
        } else {
            // For persistent storage, specify a path and create directories if needed
            let storage_path = format!("./qdrant_storage/{}", collection_name);
            std::fs::create_dir_all(&storage_path)?;
            QdrantClient::from_path(&storage_path)
                .with_timeout(std::time::Duration::from_secs(60))
                .build()?
        };

        // Create a new collection
        client
            .create_collection(&CreateCollection {
                collection_name: collection_name.to_string(),
                vectors_config: Some(VectorsConfig {
                    config: Some(vectors_config::Config::Params(VectorParams {
                        size: vector_size,
                        distance: Distance::Cosine.into(),
                        ..Default::default()
                    })),
                }),
                ..Default::default()
            })
            .await?;

        Ok(Self {
            client,
            collection_name: collection_name.to_string(),
        })
    }

    pub async fn add_embedding(&self, id: u64, embedding: Vec<f32>) -> Result<()> {
        let point = PointStruct {
            id: Some(id.into()),
            vectors: Some(embedding.into()),
            payload: None,
        };

        self.client
            .upsert_points(self.collection_name.as_str(), None, vec![point], None)
            .await?;

        Ok(())
    }

    pub async fn search_similar(&self, query_embedding: Vec<f32>, limit: u64) -> Result<Vec<ScoredPoint>> {
        let search_result = self.client
            .search_points(&SearchPoints {
                collection_name: self.collection_name.clone(),
                vector: query_embedding,
                limit: limit as u64,
                ..Default::default()
            })
            .await?;

        Ok(search_result.result)
    }
}



// Example usage
#[tokio::test]
async fn test_embedding_store() -> Result<()> {
    let store = EmbeddingStore::new("test_collection", 384, true).await?;
    
    // Add some embeddings
    store.add_embedding(1, vec![0.1, 0.2, 0.3]).await?;
    store.add_embedding(2, vec![0.4, 0.5, 0.6]).await?;
    
    // Search for similar embeddings
    let results = store.search_similar(vec![0.1, 0.2, 0.3], 5).await?;
    println!("Search results: {:?}", results);
    
    Ok(())
}