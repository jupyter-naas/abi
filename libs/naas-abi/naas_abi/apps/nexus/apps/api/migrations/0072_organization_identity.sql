-- An organization's identity (Organization Settings > General): its legal name and
-- registration, website, contact address and postal address. Every column is optional
-- and edited in the app; the configuration's seeding does not set them.
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS legal_name VARCHAR(200);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS registration_number VARCHAR(100);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS vat_number VARCHAR(100);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS website TEXT;
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS contact_email VARCHAR(254);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(200);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS address_line2 VARCHAR(200);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS country VARCHAR(100);
