-- Migration: Add suggestions and intents columns to agent_configs table

ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS suggestions JSONB;
ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS intents JSONB;

COMMENT ON COLUMN agent_configs.suggestions IS 'Suggested prompts for the agent (list of {label, value} objects)';
COMMENT ON COLUMN agent_configs.intents IS 'Agent intents (list of intent descriptor objects)';
