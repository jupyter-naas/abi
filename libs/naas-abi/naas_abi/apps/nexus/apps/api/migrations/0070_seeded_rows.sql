-- The organizations and workspaces the configuration's seeding made (core/org_seed.py).
-- Seeding updates only those, never a row a person created with the same slug. Rows
-- older than this column stay NULL until seeding finds them, once, where it made them.
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS seeded BOOLEAN;
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS seeded BOOLEAN;
