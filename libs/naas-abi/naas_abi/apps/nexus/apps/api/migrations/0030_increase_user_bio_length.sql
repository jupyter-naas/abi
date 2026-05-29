-- Migration: Increase user bio max length from 1000 to 2000 characters
-- Date: 2026-05-29
-- @dialect: postgresql
-- SQLite treats VARCHAR(n) as TEXT with no length limit, so this is a no-op there.

ALTER TABLE users ALTER COLUMN bio TYPE VARCHAR(2000);
