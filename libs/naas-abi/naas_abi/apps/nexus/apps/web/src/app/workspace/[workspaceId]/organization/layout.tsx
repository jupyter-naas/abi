'use client';

import { useParams, usePathname } from 'next/navigation';
import { OrgSettingsRedirect } from '@/components/settings/org-settings-redirect';

const LEGACY_SECTION: Record<string, string> = {
  '/organization': 'general',
  '/organization/workspaces': 'workspaces',
  '/organization/branding': 'branding',
  '/organization/users': 'users',
  '/organization/admins': 'users',
  '/organization/domains': 'domains',
  '/organization/billing': 'billing',
};

/** Legacy workspace organization settings: redirect to Organization Settings. */
export default function LegacyWorkspaceOrganizationLayout() {
  const params = useParams();
  const pathname = usePathname() ?? '';
  const workspaceId = params.workspaceId as string;
  const prefix = `/workspace/${workspaceId}`;
  const suffix = pathname.startsWith(prefix) ? pathname.slice(prefix.length) : '/organization';
  const path = LEGACY_SECTION[suffix] ?? 'general';

  return <OrgSettingsRedirect workspaceId={workspaceId} path={path} />;
}