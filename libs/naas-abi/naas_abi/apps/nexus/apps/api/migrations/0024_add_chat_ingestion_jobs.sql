CREATE TABLE chat_ingestion_jobs (
    id VARCHAR PRIMARY KEY,
    conversation_id VARCHAR NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type VARCHAR NOT NULL DEFAULT 'my_drive',
    source_path TEXT NOT NULL,
    embedding_model VARCHAR NOT NULL DEFAULT 'hash-v1',
    embedding_dimension INTEGER NOT NULL DEFAULT 256,
    status VARCHAR NOT NULL DEFAULT 'queued',
    progress INTEGER,
    cache_hit BOOLEAN,
    file_sha256 VARCHAR,
    collection_name VARCHAR,
    chunks_count INTEGER,
    error_code VARCHAR,
    error_message TEXT,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITHOUT TIME ZONE,
    finished_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX idx_chat_ingestion_jobs_conversation_id
    ON chat_ingestion_jobs(conversation_id);

CREATE INDEX idx_chat_ingestion_jobs_workspace_id
    ON chat_ingestion_jobs(workspace_id);

CREATE INDEX idx_chat_ingestion_jobs_user_id
    ON chat_ingestion_jobs(user_id);

CREATE INDEX idx_chat_ingestion_jobs_status
    ON chat_ingestion_jobs(status);

CREATE INDEX idx_chat_ingestion_jobs_created_at
    ON chat_ingestion_jobs(created_at DESC);
