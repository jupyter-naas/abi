'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { RolesAndPermissions } from '@/components/access/roles-and-permissions';
import { organizationAccessScope, workspaceAccessScope } from '@/components/access/access-scope';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import '../components/org-settings-components.css';

type OrgWorkspace = { id: string; name: string };

/**
 * Organization Settings › Roles & permissions: the shared Roles & permissions UI at the
 * organization's scope, with each of its workspaces one pick away. IAM decides what the
 * caller sees at each.
 */
export default function OrgRolesPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { authFetch } = await import('@/stores/auth');
        const response = await authFetch(`/api/organizations/${orgId}/workspaces`);
        if (response.ok && !cancelled) setWorkspaces((await response.json()) as OrgWorkspace[]);
      } catch (e) {
        console.error('Failed to fetch org workspaces:', e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  const scopes = useMemo(
    () => [
      organizationAccessScope(orgId, 'This organization'),
      ...workspaces.map((w) => workspaceAccessScope(orgId, w.id, `Workspace: ${w.name}`)),
    ],
    [orgId, workspaces],
  );

  return (
    <div className="org-settings-roles-page">
      <OrgSettingsPageHeader
        title="Roles & permissions"
        subtitle="Who holds which role or policy in this organization and its workspaces, and its groups and policies"
      />
      <RolesAndPermissions scopes={scopes} />
    </div>
  );
}
