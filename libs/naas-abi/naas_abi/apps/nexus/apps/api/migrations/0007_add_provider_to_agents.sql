-- Migration: Add provider column to agent_configs table
-- This stores which API provider the model belongs to (xai, openai, anthropic, etc.)

ALTER TABLE agent_configs 
ADD COLUMN provider VARCHAR(50);

CREATE INDEX idx_agent_configs_provider ON agent_configs(provider);
