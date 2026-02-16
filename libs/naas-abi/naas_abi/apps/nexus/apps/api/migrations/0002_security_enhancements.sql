-- Security Enhancements Migration
-- Adds: refresh tokens, audit logs, rate limiting, revoked tokens
-- Created: 2026-02-08

-- ============================================
-- Refresh Tokens Table
-- ============================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE, -- SHA-256 hash of the refresh token
    access_token_jti TEXT, -- JTI (JWT ID) of the associated access token
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMP,
    revoked_at TIMESTAMP,
    revoked_reason TEXT,
    user_agent TEXT,
    ip_address TEXT
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at);

-- ============================================
-- Revoked Access Tokens (for immediate invalidation)
-- ============================================
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY, -- JWT ID
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    revoked_at TIMESTAMP NOT NULL DEFAULT (NOW()),
    revoked_reason TEXT,
    expires_at TIMESTAMP NOT NULL -- Keep until token would naturally expire
);

CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user ON revoked_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires ON revoked_tokens(expires_at);

-- ============================================
-- Audit Logs
-- ============================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL, -- 'login', 'logout', 'register', 'password_change', 'token_refresh', etc.
    resource_type TEXT, -- 'user', 'workspace', 'conversation', etc.
    resource_id TEXT,
    details TEXT, -- JSON with additional context
    ip_address TEXT,
    user_agent TEXT,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);

-- ============================================
-- Rate Limiting (in-memory alternative via timestamp tracking)
-- ============================================
CREATE TABLE IF NOT EXISTS rate_limit_events (
    id TEXT PRIMARY KEY,
    identifier TEXT NOT NULL, -- IP address or user_id
    endpoint TEXT NOT NULL, -- '/api/auth/login', '/api/auth/register', etc.
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_identifier ON rate_limit_events(identifier, endpoint, created_at DESC);

-- ============================================
-- Password Change History (for session invalidation)
-- ============================================
CREATE TABLE IF NOT EXISTS password_changes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    changed_at TIMESTAMP NOT NULL DEFAULT (NOW()),
    ip_address TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_password_changes_user ON password_changes(user_id);
CREATE INDEX IF NOT EXISTS idx_password_changes_date ON password_changes(changed_at DESC);
