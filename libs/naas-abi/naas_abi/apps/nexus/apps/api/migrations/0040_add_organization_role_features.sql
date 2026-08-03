-- Migration: Durable per-organization role -> feature overlays
-- Date: 2026-07-30
--
-- Org admins can override the deployment role_baseline for their organization.
-- Persist that overlay so it survives restarts and is shared across API workers.
-- role_baseline is a JSON object keyed by role name (owner/admin/member/viewer).

CREATE TABLE IF NOT EXISTS organization_role_features (
    organization_id VARCHAR PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    role_baseline TEXT NOT NULL,
    updated_by VARCHAR REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_organization_role_features_updated_at
    ON organization_role_features(updated_at);
