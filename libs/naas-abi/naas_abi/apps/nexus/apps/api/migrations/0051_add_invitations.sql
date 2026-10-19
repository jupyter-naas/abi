-- Invitations (subtask 10 of #44): an email invited to an organization and/or a
-- workspace through one identity provider, before the person has an account.
-- IAM holds the roles as pending grants (grant_ids) until they sign in with the
-- address verified; this table is who invited whom, where, and as what.
CREATE TABLE IF NOT EXISTS invitations (
    id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(320) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    organization_id VARCHAR(255) REFERENCES organizations(id) ON DELETE CASCADE,
    org_role VARCHAR(16),
    workspace_id VARCHAR(255) REFERENCES workspaces(id) ON DELETE CASCADE,
    workspace_role VARCHAR(16),
    invited_by VARCHAR(255),
    grant_ids TEXT NOT NULL DEFAULT '[]',
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP,
    accepted_user_id VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS idx_invitations_email_provider ON invitations(email, provider, status);
CREATE INDEX IF NOT EXISTS idx_invitations_organization_id ON invitations(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_invitations_workspace_id ON invitations(workspace_id, status);
