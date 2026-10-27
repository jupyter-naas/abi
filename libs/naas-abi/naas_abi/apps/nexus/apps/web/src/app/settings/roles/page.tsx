'use client';

import '../system/access/access.css';

import { useState } from 'react';
import { AccessTab } from '../system/access/access';
import { SystemFrame, SystemRefresh } from '../system/system';

/**
 * The platform's roles and permissions: today's Access UI (policies, attachments,
 * groups, service accounts, approvals, simulator, audit), each section shown when
 * IAM says the caller may list it. Refresh reloads it, for a change made from the CLI
 * or another tab. The shared Roles & permissions UI replaces it.
 */
export default function PlatformRolesPage() {
  const [nonce, setNonce] = useState(0);
  return (
    <SystemFrame
      title="Roles & permissions"
      subtitle="Policies, who holds them, groups, service accounts and module approvals, as IAM lets you see them"
      actions={<SystemRefresh onClick={() => setNonce((n) => n + 1)} />}
    >
      <AccessTab nonce={nonce} />
    </SystemFrame>
  );
}
