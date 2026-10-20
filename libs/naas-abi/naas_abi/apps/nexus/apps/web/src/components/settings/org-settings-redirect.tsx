'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { SettingsLoading } from '@/components/settings/settings-ui';
import { useWorkspaceStore } from '@/stores/workspace';

/**
 * Old workspace settings pages that moved to Organization Settings: send the
 * visitor to the same page of the workspace's organization.
 */
export function OrgSettingsRedirect({
  workspaceId,
  path,
  query,
}: {
  workspaceId: string;
  /** Path below ``/organizations/<org>/settings/``, e.g. ``servers``. */
  path: string;
  query?: string;
}) {
  const router = useRouter();
  const workspaces = useWorkspaceStore((state) => state.workspaces);
  const organizationId = workspaces.find((workspace) => workspace.id === workspaceId)?.organizationId;
  const loaded = workspaces.length > 0;

  useEffect(() => {
    if (organizationId) {
      router.replace(`/organizations/${organizationId}/settings/${path}${query ? `?${query}` : ''}`);
    } else if (loaded) {
      router.replace('/organizations');
    }
  }, [organizationId, loaded, path, query, router]);

  return <SettingsLoading />;
}
