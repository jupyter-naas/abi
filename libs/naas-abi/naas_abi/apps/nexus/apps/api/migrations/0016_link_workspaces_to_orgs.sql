-- Migration: Link existing workspaces to their organizations
-- This fixes workspaces that were created before the organization feature

UPDATE workspaces SET organization_id = 'org-techcorp' WHERE id = 'workspace-platform';
UPDATE workspaces SET organization_id = 'org-techcorp' WHERE id = 'workspace-techcorp';
UPDATE workspaces SET organization_id = 'org-globalconsulting' WHERE id = 'workspace-consulting';
UPDATE workspaces SET organization_id = 'org-innovate' WHERE id = 'workspace-innovate';
UPDATE workspaces SET organization_id = 'org-researchlab' WHERE id = 'workspace-research';
