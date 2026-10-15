'use client';

import { useParams } from 'next/navigation';
import { OrgSettingsRedirect } from '@/components/settings/org-settings-redirect';

/** Services moved to Organization Settings > Services; keep the old URL working. */
export default function ServiceRedirect() {
  const params = useParams();
  const workspaceId = params?.workspaceId as string;
  const serviceId = params?.serviceId as string;
  return (
    <OrgSettingsRedirect workspaceId={workspaceId} path={`services/${encodeURIComponent(serviceId)}`} />
  );
}
