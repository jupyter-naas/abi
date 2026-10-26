-- Migration: optional workspace catalog seed (UI-defined instances at create time)
-- Date: 2026-10-22
--
-- JSON object: agents, apps, ontologies, default_agent, graphs, maps.
-- When set, merges with (or overrides) deployment config seeds for that slug.

ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS catalog_seed TEXT;
