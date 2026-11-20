-- What analytics count of a chat message, written with its metadata by the chat
-- adapter instead of parsed from the metadata JSON at read time: its feedback
-- ("like" / "dislike", and the type of a dislike) and the tools it called.
-- Messages of the last 45 days written before this migration are indexed once at
-- start (analytics job message_facts_v1), and those written since then by a rolling
-- deploy's old processes thirty minutes later (message_facts_v2). The migration runner
-- skips these ALTERs once the columns exist, so a start never locks messages.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback VARCHAR(16);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback_type VARCHAR(100);

CREATE TABLE IF NOT EXISTS message_tools (
    message_id VARCHAR NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    tool_name VARCHAR(200) NOT NULL,
    uses INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (message_id, tool_name)
);
