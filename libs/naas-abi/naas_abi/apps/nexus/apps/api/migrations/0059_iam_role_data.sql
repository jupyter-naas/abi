-- Memberships, owners and superadmin flags moved into IAM:
-- role attachments are the only record of who holds which role. This table
-- marks the one-time move, so a stale row of the tables below is never read
-- back into IAM after someone changed a role through it.
CREATE TABLE IF NOT EXISTS iam_migrations (
    name VARCHAR(128) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    report TEXT
);
