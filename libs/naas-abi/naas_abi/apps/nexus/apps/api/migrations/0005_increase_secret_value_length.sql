-- Migration: Increase encrypted_value column size to support longer API keys
-- Fernet encryption adds overhead, making encrypted values longer than the original
-- @dialect: postgresql
-- SQLite treats VARCHAR(255) as TEXT with no length limit, so this is a no-op there.

ALTER TABLE secrets ALTER COLUMN encrypted_value TYPE TEXT;
