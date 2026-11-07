'use client';

import { useState } from 'react';
import { RolesAndPermissions } from '@/components/access/roles-and-permissions';
import { PLATFORM_ACCESS_SCOPE } from '@/components/access/access-scope';
import { SystemFrame, SystemRefresh } from '../system/system';

const SCOPES = [PLATFORM_ACCESS_SCOPE];

/**
 * The platform's roles and permissions: the shared Roles & permissions UI at platform
 * scope. Refresh reloads it, for a change made from the CLI or another tab.
 */
export default function PlatformRolesPage() {
  const [nonce, setNonce] = useState(0);
  return (
    <SystemFrame
      title="Roles & permissions"
      subtitle="Who holds what on the platform, groups, policies, service accounts and module approvals, as IAM lets you see them"
      actions={<SystemRefresh onClick={() => setNonce((n) => n + 1)} />}
    >
      <RolesAndPermissions scopes={SCOPES} nonce={nonce} />
    </SystemFrame>
  );
}
