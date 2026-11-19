-- What analytics count of a chat message, written with its metadata by the chat
-- adapter instead of parsed from the metadata JSON at read time: its feedback
-- ("like" / "dislike", and the type of a dislike) and the tools it called.
-- Messages of the last 45 days written before this migration are indexed once at
-- start (analytics job message_facts_v1).
ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback VARCHAR(16);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback_type VARCHAR(100);

CREATE TABLE IF NOT EXISTS message_tools (
    message_id VARCHAR NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    tool_name VARCHAR(200) NOT NULL,
    uses INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (message_id, tool_name)
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages (conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_workspace_updated ON conversations (workspace_id, updated_at);
