-- Migration: Add module_path column to agent_configs table

ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS module_path TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_configs_module_path ON agent_configs(module_path);

COMMENT ON COLUMN agent_configs.module_path IS 'Python module path of the agent class (e.g. naas_abi_marketplace.applications.openrouter)';

