-- Deduplicate agent_configs rows that share (workspace_id, class_name),
-- keeping the earliest-created row, then enforce uniqueness going forward.
-- This prevents concurrent list_agents calls from inserting the same agent
-- class multiple times into the same workspace on first load.

DELETE FROM agent_configs
WHERE id NOT IN (
  SELECT DISTINCT ON (workspace_id, class_name) id
  FROM agent_configs
  WHERE class_name IS NOT NULL
  ORDER BY workspace_id, class_name, created_at ASC
)
AND class_name IS NOT NULL;

ALTER TABLE agent_configs
  ADD CONSTRAINT uq_agent_configs_workspace_class
  UNIQUE (workspace_id, class_name);
