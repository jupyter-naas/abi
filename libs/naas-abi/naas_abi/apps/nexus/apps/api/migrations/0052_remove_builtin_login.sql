-- Nexus has no login of its own any more (RFC §13, subtask 13 of #44): people sign
-- in at an identity provider. What the password, magic-link, one-time-code and
-- refresh-token logins kept goes: their tables, the unused API-key mock (personal
-- keys are IAM's), and the password hash of every user.
DROP TABLE IF EXISTS refresh_tokens;
DROP TABLE IF EXISTS revoked_tokens;
DROP TABLE IF EXISTS password_changes;
DROP TABLE IF EXISTS password_reset_tokens;
DROP TABLE IF EXISTS magic_link_tokens;
DROP TABLE IF EXISTS api_keys;
ALTER TABLE users DROP COLUMN hashed_password;
