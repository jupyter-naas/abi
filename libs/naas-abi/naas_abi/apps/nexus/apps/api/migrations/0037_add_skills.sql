-- Migration: Add skills table (user-created reusable prompt skills)
-- A skill is a named prompt invocable from the chat bar via /<slug>.
-- scope controls visibility: user (creator only), workspace, organization.

CREATE TABLE IF NOT EXISTS skills (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    organization_id VARCHAR REFERENCES organizations(id) ON DELETE SET NULL,
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    slug VARCHAR NOT NULL,
    description TEXT,
    prompt TEXT NOT NULL,
    scope VARCHAR NOT NULL DEFAULT 'user',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skills_workspace_id ON skills(workspace_id);
CREATE INDEX IF NOT EXISTS idx_skills_organization_id ON skills(organization_id);
CREATE INDEX IF NOT EXISTS idx_skills_user_id ON skills(user_id);
CREATE INDEX IF NOT EXISTS idx_skills_slug ON skills(slug);
