-- Security Enhancements Migration
-- Adds: audit logs, rate limiting
-- Created: 2026-02-08

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
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_identifier ON rate_limit_events(identifier, endpoint, created_at DESC);
