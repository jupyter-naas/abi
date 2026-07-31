-- Migration: One registry agent row per workspace
-- Date: 2026-07-31
--
-- POST /api/agents/sync used check-then-insert with no uniqueness on
-- (workspace_id, class_name). Concurrent syncs (multi-tab, multi-component
-- fetch) raced and inserted duplicate Abi/ChatGPT/etc rows.
--
-- 1) Collapse existing duplicates (prefer default, then enabled, then oldest).
-- 2) Enforce uniqueness going forward via a partial unique index so manually
--    created agents with NULL class_name remain unrestricted.

DELETE FROM agent_configs
WHERE id IN (
    SELECT id
    FROM (
        SELECT
            id,
            ROW_NUMBER() OVER (
                PARTITION BY workspace_id, class_name
                ORDER BY
                    is_default DESC,
                    enabled DESC,
                    created_at ASC,
                    id ASC
            ) AS rn
        FROM agent_configs
        WHERE class_name IS NOT NULL
          AND class_name <> ''
    ) ranked
    WHERE rn > 1
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_configs_workspace_class_name
    ON agent_configs (workspace_id, class_name)
    WHERE class_name IS NOT NULL AND class_name <> '';
