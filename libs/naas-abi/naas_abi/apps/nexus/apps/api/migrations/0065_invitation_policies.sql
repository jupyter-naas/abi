-- The policies an invitation carries for the new member beside their role (a
-- workspace's "Features of member", say): a JSON list of IAM policy ids, each
-- held as a pending grant at the invitation's scope until the first sign-in.
ALTER TABLE invitations ADD COLUMN IF NOT EXISTS policy_ids TEXT;
