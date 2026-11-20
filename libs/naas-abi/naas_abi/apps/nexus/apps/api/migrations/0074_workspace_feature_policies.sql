-- The policy Workspace settings > General writes for each feature of a workspace
-- ("Feature · <name>", owned by the workspace, a sub-policy of "<W> access"): who may
-- use the feature there is where IAM attaches it (services/feature_access). IAM holds
-- the policy; this table says which it is, never found by its name.
CREATE TABLE IF NOT EXISTS workspace_feature_policies (
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    feature VARCHAR(64) NOT NULL,
    policy_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, feature)
);
