-- The accounts ABI made at an identity provider: an invitation's provisioning created
-- them (services/invites). Platform Settings > Users changes and deletes an account at a
-- provider such as Keycloak or Zitadel only when it is here (services/accounts): one
-- that already existed in the realm is the person's, used by other applications, and
-- stays as it is when their Nexus account is deactivated or deleted.
CREATE TABLE IF NOT EXISTS provisioned_identities (
    provider VARCHAR(255) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (provider, subject)
);
