'use client';

import '../system/access/access.css';

import { AccessTab } from '../system/access/access';
import { SystemFrame } from '../system/system';

/**
 * The platform's roles and permissions: today's Access UI (policies, attachments,
 * groups, service accounts, approvals, simulator, audit), each section shown when
 * IAM says the caller may list it. The shared Roles & permissions UI replaces it.
 */
export default function PlatformRolesPage() {
  return (
    <SystemFrame
      title="Roles & permissions"
      subtitle="Policies, who holds them, groups, service accounts and module approvals, as IAM lets you see them"
    >
      <AccessTab />
    </SystemFrame>
  );
}
