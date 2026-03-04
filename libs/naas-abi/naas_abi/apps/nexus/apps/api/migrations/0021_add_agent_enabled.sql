-- Migration: Add enabled column to agent_configs table
-- Date: 2026-02-10

ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN agent_configs.enabled IS 'Whether the agent is available for use in chat';
