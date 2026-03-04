-- Migration: Increase encrypted_value column size to support longer API keys
-- Fernet encryption adds overhead, making encrypted values longer than the original

ALTER TABLE secrets ALTER COLUMN encrypted_value TYPE TEXT;
