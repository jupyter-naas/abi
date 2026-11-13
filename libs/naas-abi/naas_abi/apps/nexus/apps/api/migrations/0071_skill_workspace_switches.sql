-- An organization skill turned on or off in one workspace of its organization, by that
-- workspace's admins (services/skills): without a row, it is on wherever it is listed.
CREATE TABLE IF NOT EXISTS skill_workspace_switches (
    skill_id VARCHAR(255) NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    workspace_id VARCHAR(255) NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL,
    updated_by VARCHAR(255),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (skill_id, workspace_id)
);
