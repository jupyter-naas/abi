-- A platform admin deletes an account (Platform Settings > Users): the account at its
-- identity provider, its IAM user, attachments, memberships, sessions and keys go,
-- and what the person wrote in workspaces stays. The row stays as the author of that
-- work, retired: deleted_at says when, and its email is released (services/accounts).
ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;
