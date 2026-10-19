-- Sign-in through the engine's OIDC identity providers (RFC §12).
-- A user signed in through a provider is one row per (issuer, sub): its id is
-- its IAM principal id, which principal_id names too. Rows of the built-in
-- login keep both empty until they move to the built-in IdP (migration 0052).
ALTER TABLE users ADD COLUMN IF NOT EXISTS principal_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS idp_provider VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS idp_issuer VARCHAR(1024);
ALTER TABLE users ADD COLUMN IF NOT EXISTS idp_subject VARCHAR(255);
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_principal_id ON users(principal_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_idp_identity ON users(idp_issuer, idp_subject);

-- An email domain routes a login to a provider; none: the default provider.
-- No migration created the table before (only the ORM model declared it).
CREATE TABLE IF NOT EXISTS organization_domains (
    id VARCHAR(255) PRIMARY KEY,
    organization_id VARCHAR(255) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL UNIQUE,
    provider VARCHAR(64),
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_token VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_organization_domains_organization_id ON organization_domains(organization_id);
ALTER TABLE organization_domains ADD COLUMN IF NOT EXISTS provider VARCHAR(64);

-- A sign-in in flight: single use, ten minutes at most. The state is stored
-- hashed, and so is the browser binding (a cookie the callback must present).
CREATE TABLE IF NOT EXISTS oidc_login_requests (
    state_hash VARCHAR(64) PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    nonce VARCHAR(128) NOT NULL,
    code_verifier VARCHAR(128) NOT NULL,
    binding_hash VARCHAR(64) NOT NULL,
    next_path VARCHAR(2048),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- A browser session held by the API: the cookie carries a random secret whose
-- SHA-256 is the id. The provider's tokens are encrypted at rest and never
-- leave the API; refresh_at is when the provider must vouch for the user again
-- (ten minutes at most).
CREATE TABLE IF NOT EXISTS auth_sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    principal_id VARCHAR(255) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    group_ids TEXT NOT NULL DEFAULT '[]',
    refresh_token_enc TEXT,
    id_token_enc TEXT,
    refresh_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP,
    revoked_at TIMESTAMP,
    user_agent VARCHAR(512)
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
