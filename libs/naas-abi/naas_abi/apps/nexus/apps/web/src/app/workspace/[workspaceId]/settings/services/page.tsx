'use client';

import { useParams } from 'next/navigation';
import { OrgSettingsRedirect } from '@/components/settings/org-settings-redirect';

/** Services moved to Organization Settings > Services; keep the old URL working. */
export default function ServicesRedirect() {
  const workspaceId = useParams()?.workspaceId as string;
  return <OrgSettingsRedirect workspaceId={workspaceId} path="services" />;
}
