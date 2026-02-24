-- Migration: Add class_name column to agent_configs table
-- Stores stable ABI class reference used for in-process routing.

ALTER TABLE agent_configs
ADD COLUMN IF NOT EXISTS class_name VARCHAR(512);

CREATE INDEX IF NOT EXISTS idx_agent_configs_class_name ON agent_configs(class_name);
