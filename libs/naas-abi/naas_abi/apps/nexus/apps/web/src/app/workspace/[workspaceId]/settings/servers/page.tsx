'use client';

import { useParams } from 'next/navigation';
import { OrgSettingsRedirect } from '@/components/settings/org-settings-redirect';

/** Servers moved to Organization Settings > Servers; keep the old URL working. */
export default function ServersRedirect() {
  const workspaceId = useParams()?.workspaceId as string;
  return (
    <OrgSettingsRedirect
      workspaceId={workspaceId}
      path="servers"
      query={`workspace=${encodeURIComponent(workspaceId)}`}
    />
  );
}
