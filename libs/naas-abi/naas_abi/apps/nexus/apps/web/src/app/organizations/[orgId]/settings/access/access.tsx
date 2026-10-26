'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { createIamAdminApi } from '@/lib/iam-admin/api';
import { useIamAccess } from '@/lib/iam-admin/use-access';
import { AttachmentsPanel } from '@/app/settings/system/access/attachments/attachments-panel';
import { OrgSettingsPageHeader } from '../components/org-settings-page-header';
import { OrgSettingsSectionCard } from '../components/org-settings-section-card';
import '../components/org-settings-components.css';
import './access.css';

type OrgWorkspace = { id: string; name: string };

/** Who holds which policy in this organization and its workspaces. IAM decides every call:
 *  an organization admin attaches the roles below owner here, an owner any policy confined to
 *  the scope. Policies themselves, groups and service accounts are the platform's (System). */
export default function OrgAccessPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const api = useMemo(() => createIamAdminApi(), []);
  const [workspaces, setWorkspaces] = useState<OrgWorkspace[]>([]);
  const [scope, setScope] = useState<string | undefined>(undefined);
  const { can, loading, error } = useIamAccess(scope, api);

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
      { value: `abi:${orgId}:-`, label: 'Organization' },
      ...workspaces.map((w) => ({ value: `abi:${orgId}:${w.id}`, label: `Workspace: ${w.name}` })),
    ],
    [orgId, workspaces],
  );

  if (!loading && (error || !can('iam:ListAttachments'))) {
    return (
      <div className="org-settings-access-page">
        <OrgSettingsPageHeader title="Access" subtitle="Who holds which policy in this organization" />
        <p className="org-settings-access-hint" role="status">
          {error ?? 'You do not have permission to see who holds policies here.'}
        </p>
      </div>
    );
  }

  return (
    <div className="org-settings-access-page">
      <OrgSettingsPageHeader
        title="Access"
        subtitle="Who holds which policy in this organization and its workspaces"
      />
      <OrgSettingsSectionCard padded stack>
        <p className="org-settings-access-hint">
          A policy attached here applies only inside the scope you pick. Attach to a person, a group or a
          service account by its IAM id.
        </p>
        <AttachmentsPanel api={api} scopes={scopes} can={can} onScopeChange={setScope} />
      </OrgSettingsSectionCard>
    </div>
  );
}
