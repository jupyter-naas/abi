-- The member profile an organization admin set when inviting someone who has no
-- account yet (Organization Settings > Users > Create user): a JSON object kept
-- with the invitation and written as the person's profile in that organization
-- at their first sign-in, when their account exists.
ALTER TABLE invitations ADD COLUMN IF NOT EXISTS profile TEXT;
