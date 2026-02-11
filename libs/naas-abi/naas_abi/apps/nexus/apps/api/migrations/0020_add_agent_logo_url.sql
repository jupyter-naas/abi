-- Migration: Add logo_url column to agent_configs table
-- Date: 2026-02-10

ALTER TABLE agent_configs ADD COLUMN IF NOT EXISTS logo_url TEXT;

COMMENT ON COLUMN agent_configs.logo_url IS 'URL to agent/provider logo image (optional)';
