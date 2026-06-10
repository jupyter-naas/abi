-- Migration: Add module_path to conversations for project scoping
-- Date: 2026-06-10

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS module_path VARCHAR(500) NULL;
CREATE INDEX IF NOT EXISTS idx_conversations_module_path ON conversations(workspace_id, module_path) WHERE module_path IS NOT NULL;
