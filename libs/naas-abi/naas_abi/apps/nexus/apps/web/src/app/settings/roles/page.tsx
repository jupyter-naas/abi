'use client';

import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { RolesAndPermissions } from '@/components/access/roles-and-permissions';
import { PLATFORM_ACCESS_SCOPE } from '@/components/access/access-scope';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';

const SCOPES = [PLATFORM_ACCESS_SCOPE];

/**
 * The platform's roles and permissions: the shared Roles & permissions UI at platform
 * scope, laid out like the organization's page of the same name. Refresh reloads it,
 * for a change made from the CLI or another tab.
 */
export default function PlatformRolesPage() {
  const [nonce, setNonce] = useState(0);
  return (
    <div className="org-settings-roles-page">
      <OrgSettingsPageHeader
        title="Roles & permissions"
        subtitle="Who holds what on the platform, groups, policies, service accounts and module approvals, as IAM lets you see them"
        actions={
          <button
            type="button"
            className="org-settings-users-secondary-button"
            data-action="refresh"
            onClick={() => setNonce((n) => n + 1)}
            title="Refresh"
            aria-label="Refresh"
          >
            <RefreshCw size={16} />
          </button>
        }
      />
      <RolesAndPermissions scopes={SCOPES} nonce={nonce} />
    </div>
  );
}
