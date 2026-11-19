-- An organization's time zone (Organization Settings > General): an IANA name such as
-- Europe/Paris. Its analytics periods (today, yesterday, this week, this month) and
-- those of its workspaces start at midnight there. Existing organizations get UTC.
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'UTC';
