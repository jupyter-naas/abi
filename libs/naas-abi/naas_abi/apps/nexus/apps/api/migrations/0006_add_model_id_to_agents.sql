-- Migration: Add model_id column to agent_configs table
-- This allows agents to be linked to specific models from the registry

ALTER TABLE agent_configs 
ADD COLUMN model_id VARCHAR(255);

CREATE INDEX idx_agent_configs_model_id ON agent_configs(model_id);
