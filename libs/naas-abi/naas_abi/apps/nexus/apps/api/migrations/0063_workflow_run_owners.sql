-- Who started a workflow or pipeline run from a workspace (module scopes:
-- module:RunWorkflow / RunPipeline). Job runs carry no owner of their own: a
-- user reads the runs they started here, in the workspace they started them in
-- (module:ReadWorkflowRuns / ReadPipelineRuns).
CREATE TABLE IF NOT EXISTS workflow_run_owners (
    module_id VARCHAR(255) NOT NULL,
    run_id VARCHAR(255) NOT NULL,
    workflow VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (module_id, run_id)
);
CREATE INDEX IF NOT EXISTS idx_workflow_run_owners_user ON workflow_run_owners(user_id, workspace_id, started_at);
