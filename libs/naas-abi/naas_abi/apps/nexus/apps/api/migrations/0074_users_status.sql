-- A person is a users row from the moment they are invited (services/people): the row
-- is 'invited' until their first sign-in makes it 'active' (services/oidc), and
-- activated_at says when. Every existing row is a person who exists already: 'active'.
ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'active';
ALTER TABLE users ADD COLUMN IF NOT EXISTS activated_at TIMESTAMP;
