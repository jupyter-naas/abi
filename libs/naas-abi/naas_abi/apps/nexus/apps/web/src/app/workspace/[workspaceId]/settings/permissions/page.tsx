'use client';

import { useMemo } from 'react';
import { useParams } from 'next/navigation';
import { RolesAndPermissions } from '@/components/access/roles-and-permissions';
import { workspaceAccessScope } from '@/components/access/access-scope';
import { SettingsPageHeader } from '@/components/settings/settings-ui';
import { workspaceOrganization } from '@/components/shell/settings-nav';
import { useWorkspaceStore } from '@/stores/workspace';

/**
 * Workspace Settings › Roles & permissions: the shared Roles & permissions UI at this
 * workspace's scope. The menu shows it to whoever holds an `iam:` action here; IAM decides
 * every section and button.
 */
export default function WorkspaceRolesPage() {
  const workspaceId = useParams()?.workspaceId as string;
  // The path names the workspace by its id or its slug; IAM by its id.
  const workspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === workspaceId || w.slug === workspaceId));
  const org = workspaceOrganization(workspace);
  const id = workspace?.id;
  const name = workspace?.name || 'This workspace';
  const scopes = useMemo(() => (id ? [workspaceAccessScope(org, id, name)] : []), [org, id, name]);

  return (
    <div className="space-y-6">
      <SettingsPageHeader
        title="Roles & permissions"
        description="Who holds which role or policy in this workspace, its groups and its policies"
      />
      {workspace ? <RolesAndPermissions scopes={scopes} /> : <p className="text-sm text-muted-foreground">Loading…</p>}
    </div>
  );
}
