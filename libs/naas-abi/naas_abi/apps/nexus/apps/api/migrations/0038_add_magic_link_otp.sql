-- Email OTP codes ride on magic_link_tokens (same challenge, two verify paths).
ALTER TABLE magic_link_tokens
    ADD COLUMN IF NOT EXISTS otp_code_hash TEXT;

ALTER TABLE magic_link_tokens
    ADD COLUMN IF NOT EXISTS otp_attempts INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_magic_link_tokens_user_unused
    ON magic_link_tokens (user_id, created_at DESC)
    WHERE used = FALSE;
